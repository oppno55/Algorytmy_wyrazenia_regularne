import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QFileDialog, 
                             QStatusBar, QHBoxLayout, QVBoxLayout, QCheckBox, 
                             QLabel, QScrollArea, QFrame, QPushButton, QColorDialog,
                             QSpinBox)
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QPixmap, QPolygonF
from PyQt5.QtCore import Qt, QPointF

# ==========================================
# 1. MODELE DANYCH I INDEKS PRZESTRZENNY
# ==========================================

class BoundingBox:
    __slots__ = ['min_x', 'min_y', 'max_x', 'max_y']
    def __init__(self, min_x=float('inf'), min_y=float('inf'), max_x=float('-inf'), max_y=float('-inf')):
        self.min_x = min_x
        self.min_y = min_y
        self.max_x = max_x
        self.max_y = max_y

    def expand(self, x, y):
        if x < self.min_x: self.min_x = x
        if x > self.max_x: self.max_x = x
        if y < self.min_y: self.min_y = y
        if y > self.max_y: self.max_y = y

    def intersects(self, other):
        if self.max_x < other.min_x or self.min_x > other.max_x: return False
        if self.max_y < other.min_y or self.min_y > other.max_y: return False
        return True

class Feature:
    __slots__ = ['category', 'geom_type', 'bbox', 'qt_geom']
    def __init__(self, category, geom_type, coords):
        self.category = category 
        self.geom_type = geom_type
        self.bbox = BoundingBox()
        
        # PL-1992: pierwsza współrzędna (x) to północ, druga (y) to wschód[cite: 1]
        # Dla Qt: x (poziom) to wschód mapy, y (pion) to -północ mapy.
        if self.geom_type == '_P':
            x, y = coords[0]
            self.qt_geom = QPointF(y, -x)
            self.bbox.expand(x, y)
        else:
            self.qt_geom = QPolygonF()
            for x, y in coords:
                self.qt_geom.append(QPointF(y, -x))
                self.bbox.expand(x, y)

class SpatialIndex:
    def __init__(self, cell_size=2000.0): 
        self.cell_size = cell_size
        self.grid = defaultdict(list)
        self.all_objects = []

    def insert(self, feature):
        self.all_objects.append(feature)
        min_col = int(feature.bbox.min_y // self.cell_size)
        max_col = int(feature.bbox.max_y // self.cell_size)
        min_row = int(feature.bbox.min_x // self.cell_size)
        max_row = int(feature.bbox.max_x // self.cell_size)

        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                self.grid[(row, col)].append(feature)

    def query(self, bbox):
        if bbox.min_x == float('-inf'):
            return self.all_objects

        min_col = int(bbox.min_y // self.cell_size)
        max_col = int(bbox.max_y // self.cell_size)
        min_row = int(bbox.min_x // self.cell_size)
        max_row = int(bbox.max_x // self.cell_size)

        result = set()
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                if (row, col) in self.grid:
                    for feature in self.grid[(row, col)]:
                        if feature.bbox.intersects(bbox):
                            result.add(feature)
        return list(result)

# ==========================================
# 2. EKSPRESOWY PARSER GML
# ==========================================

class GMLParser:
    @staticmethod
    def parse_file(filepath):
        features = []
        context = ET.iterparse(filepath, events=('start', 'end'))
        context = iter(context)
        try:
            event, root = next(context)
        except StopIteration:
            return []

        filename = filepath.split('/')[-1].split('\\')[-1]
        is_polygon = 'Polygon' in filepath
        is_point = 'Point' in filepath

        if 'OT_' in filename:
            idx = filename.find('OT_')
            category = filename[idx+3 : idx+5] 
        else:
            category = 'UN'

        for event, elem in context:
            if event == 'end':
                # Szukamy geometrii
                if 'posList' in elem.tag or 'pos' in elem.tag:
                    if elem.text:
                        coords_raw = elem.text.strip().split()
                        
                        # Ręczne składanie par rozwiązuje potencjalne problemy z ZIP
                        coords = []
                        for i in range(0, len(coords_raw), 2):
                            if i + 1 < len(coords_raw):
                                coords.append((float(coords_raw[i]), float(coords_raw[i+1])))
                        
                        if not coords:
                            continue
                            
                        # Przypisujemy prawidłowo czy to poligon, czy linia[cite: 1]
                        geom_type = '_A' if is_polygon or len(coords) > 2 else '_L'
                        if is_point or len(coords) == 1:
                            geom_type = '_P'
                            
                        features.append(Feature(category, geom_type, coords))
                
                elem.clear() 
                root.clear() 
                
        return features

# ==========================================
# 3. KANWA MAPY - BUFOROWANIE I CACHE
# ==========================================

class MapCanvas(QWidget):
    def __init__(self, status_bar):
        super().__init__()
        self.status_bar = status_bar
        self.spatial_index = SpatialIndex()
        
        self.scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        
        self.global_bbox = BoundingBox()
        self.visible_layers = set()
        
        self.cached_pixmap = None
        self.is_dragging = False
        self.drag_start = None
        self.drag_delta_x = 0
        self.drag_delta_y = 0
        
        self.layer_styles = {
            'BU': {'color': QColor(210, 100, 100), 'width': 1},
            'PT': {'color': QColor(160, 220, 160), 'width': 1},
            'SW': {'color': QColor(100, 150, 255), 'width': 2},
            'SK': {'color': QColor(80, 80, 80), 'width': 2},
            'SU': {'color': QColor(255, 165, 0), 'width': 1},
            'AD': {'color': QColor(200, 150, 200), 'width': 3},
            'default': {'color': QColor(150, 150, 150), 'width': 1}
        }

    def load_data(self, filepaths):
        for path in filepaths:
            self.status_bar.showMessage(f"Wczytywanie: {path.split('/')[-1]}...")
            QApplication.processEvents()
            
            new_features = GMLParser.parse_file(path)
            for f in new_features:
                self.spatial_index.insert(f)
                self.global_bbox.expand(f.bbox.min_x, f.bbox.min_y)
                self.global_bbox.expand(f.bbox.max_x, f.bbox.max_y)
                self.visible_layers.add(f.category)
            
        self.fit_to_screen()
        self.redraw_map()

    def fit_to_screen(self):
        if self.global_bbox.min_x == float('inf'): return
        w, h = self.width(), self.height()
        bbox_w = self.global_bbox.max_y - self.global_bbox.min_y
        bbox_h = self.global_bbox.max_x - self.global_bbox.min_x
        
        scale_x = w / bbox_w if bbox_w > 0 else 1
        scale_y = h / bbox_h if bbox_h > 0 else 1
        self.scale = min(scale_x, scale_y) * 0.9 
        
        self.offset_y = -self.global_bbox.min_y * self.scale + (w - bbox_w * self.scale) / 2
        self.offset_x = self.global_bbox.max_x * self.scale + (h - bbox_h * self.scale) / 2

    def to_map(self, screen_x, screen_y):
        y = (screen_x - self.offset_y) / self.scale
        x = -(screen_y - self.offset_x) / self.scale
        return x, y

    def redraw_map(self):
        """Właściwe, ciężkie renderowanie do bufora"""
        if self.global_bbox.min_x == float('inf') or self.width() == 0: 
            return
            
        start_time = time.time()
        
        self.cached_pixmap = QPixmap(self.size())
        self.cached_pixmap.fill(Qt.white)
        painter = QPainter(self.cached_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        map_x1, map_y1 = self.to_map(0, 0)
        map_x2, map_y2 = self.to_map(self.width(), self.height())
        
        view_bbox = BoundingBox(
            min_x=min(map_x1, map_x2), min_y=min(map_y1, map_y2),
            max_x=max(map_x1, map_x2), max_y=max(map_y1, map_y2)
        )
        
        visible_features = self.spatial_index.query(view_bbox)
        drawing_order = {'PT': 1, 'SW': 2, 'AD': 3, 'SK': 4, 'SU': 5, 'BU': 6, 'OI': 7, 'default': 99}
        visible_features.sort(key=lambda f: drawing_order.get(f.category, drawing_order['default']))
        
        painter.translate(self.offset_x, self.offset_y)
        painter.scale(self.scale, self.scale)
        
        # Wyłączono ukrywanie budynków i punktów dla pewności, że wszystkie obiekty trafiają na płótno
        # Obiekty będą malowane zawsze
        min_size = 0.5 / self.scale
        
        drawn_count = 0
        
        for feature in visible_features:
            if feature.category not in self.visible_layers: continue
                
            # Odrzucanie na wczesnym etapie obiektów zajmujących ekstremalnie mało miejsca
            if feature.geom_type == '_A':
                if (feature.bbox.max_y - feature.bbox.min_y) < min_size and \
                   (feature.bbox.max_x - feature.bbox.min_x) < min_size:
                    continue
                
            style = self.layer_styles.get(feature.category, self.layer_styles['default'])
            color = style['color']
            pen = QPen(color, style['width'])
            pen.setCosmetic(True) 
            
            if feature.geom_type == '_P':
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(color))
                r = 3 / self.scale 
                painter.drawEllipse(feature.qt_geom, r, r) 
                
            elif feature.geom_type == '_L':
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawPolyline(feature.qt_geom)
                    
            elif feature.geom_type == '_A':
                painter.setPen(pen)
                painter.setBrush(QBrush(color))
                painter.drawPolygon(feature.qt_geom)
                
            drawn_count += 1
                
        painter.end()
        self.update()
        
        draw_time_ms = (time.time() - start_time) * 1000
        self.status_bar.showMessage(f"Przerysowano: {drawn_count} ob. | Czas renderu: {draw_time_ms:.1f} ms | Skala: {self.scale:.2f}")

    def paintEvent(self, event):
        """Błyskawiczne odrysowanie bufora na ekranie"""
        if not self.cached_pixmap:
            return
            
        painter = QPainter(self)
        if self.is_dragging:
            painter.drawPixmap(self.drag_delta_x, self.drag_delta_y, self.cached_pixmap)
        else:
            painter.drawPixmap(0, 0, self.cached_pixmap)

    def wheelEvent(self, event):
        zoom_factor = 1.2 if event.angleDelta().y() > 0 else 0.8
        mouse_pos = event.pos()
        
        old_map_y = (mouse_pos.x() - self.offset_y) / self.scale
        old_map_x = (mouse_pos.y() - self.offset_x) / self.scale
        
        self.scale *= zoom_factor
        self.offset_y = mouse_pos.x() - (old_map_y * self.scale)
        self.offset_x = mouse_pos.y() - (old_map_x * self.scale)
        
        self.redraw_map()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.drag_start = event.pos()
            self.drag_delta_x = 0
            self.drag_delta_y = 0

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            delta = event.pos() - self.drag_start
            self.drag_delta_x = delta.x()
            self.drag_delta_y = delta.y()
            self.update() 

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
            self.offset_x += self.drag_delta_y
            self.offset_y += self.drag_delta_x
            self.redraw_map()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.redraw_map()

# ==========================================
# 4. GŁÓWNE OKNO APLIKACJI I UI
# ==========================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Super-Optymalna Przeglądarka BDOT10k")
        self.resize(1200, 800)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.canvas = MapCanvas(self.status_bar)
        main_layout.addWidget(self.canvas, stretch=4)
        
        side_panel = QFrame()
        side_panel.setFixedWidth(300)
        self.side_layout = QVBoxLayout(side_panel)
        
        btn_load = QPushButton("Wczytaj pliki GML")
        btn_load.clicked.connect(self.open_files)
        self.side_layout.addWidget(btn_load)
        
        self.side_layout.addWidget(QLabel("<b>Narzędzia i Warstwy:</b>"))
        
        self.layers_layout = QVBoxLayout()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_widget.setLayout(self.layers_layout)
        scroll_area.setWidget(scroll_widget)
        
        self.side_layout.addWidget(scroll_area)
        main_layout.addWidget(side_panel, stretch=1)
        
        self.setCentralWidget(central_widget)

    def open_files(self):
        filepaths, _ = QFileDialog.getOpenFileNames(self, "Wybierz pliki", "", "GML (*.gml *.xml);;Wszystkie (*)")
        if filepaths:
            self.canvas.load_data(filepaths)
            self.update_layer_panel()

    def update_layer_panel(self):
        for i in reversed(range(self.layers_layout.count())): 
            self.layers_layout.itemAt(i).widget().setParent(None)
            
        cat_names = {'BU': 'Budynki', 'PT': 'Pokrycie terenu', 'SW': 'Wody', 'SK': 'Komunikacja', 'SU': 'Sieci uzbroj.', 'AD': 'Granice admin.', 'OI': 'Inne'}
        
        for category in sorted(list(self.canvas.visible_layers)):
            layer_widget = QWidget()
            h_layout = QHBoxLayout(layer_widget)
            h_layout.setContentsMargins(0,0,0,0)
            
            cb = QCheckBox(cat_names.get(category, category))
            cb.setChecked(True)
            cb.stateChanged.connect(lambda state, c=category: self.set_layer_vis(c, state == Qt.Checked))
            
            # Bezpieczne pobranie stylów (rozwiązuje błąd KeyError: 'PZ')
            style = self.canvas.layer_styles.get(category, self.canvas.layer_styles['default'])
            
            btn_color = QPushButton()
            btn_color.setFixedWidth(20)
            btn_color.setStyleSheet(f"background-color: {style['color'].name()};")
            btn_color.clicked.connect(lambda checked, c=category, btn=btn_color: self.change_color(c, btn))
            
            spin_width = QSpinBox()
            spin_width.setRange(1, 10)
            spin_width.setValue(style['width'])
            spin_width.valueChanged.connect(lambda val, c=category: self.change_width(c, val))
            
            h_layout.addWidget(cb)
            h_layout.addWidget(btn_color)
            h_layout.addWidget(spin_width)
            self.layers_layout.addWidget(layer_widget)
            
        self.layers_layout.addStretch()

    def set_layer_vis(self, category, is_visible):
        if is_visible:
            self.canvas.visible_layers.add(category)
        else:
            self.canvas.visible_layers.discard(category)
        self.canvas.redraw_map()

    def change_color(self, category, button):
        current_color = self.canvas.layer_styles.get(category, self.canvas.layer_styles['default'])['color']
        new_color = QColorDialog.getColor(current_color, self, "Wybierz kolor warstwy")
        if new_color.isValid():
            # Przypisz nowy kolor, jeśli nie istnieje jeszcze własny wpis dla tej kategorii to go utwórz
            if category not in self.canvas.layer_styles:
                self.canvas.layer_styles[category] = self.canvas.layer_styles['default'].copy()
            self.canvas.layer_styles[category]['color'] = new_color
            button.setStyleSheet(f"background-color: {new_color.name()};")
            self.canvas.redraw_map()

    def change_width(self, category, value):
        if category not in self.canvas.layer_styles:
            self.canvas.layer_styles[category] = self.canvas.layer_styles['default'].copy()
        self.canvas.layer_styles[category]['width'] = value
        self.canvas.redraw_map()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())