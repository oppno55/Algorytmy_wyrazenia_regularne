#include <iostream>
#include <vector>
#include <string>
#include <set>

using namespace std;

//(A*(B|C)*AC) - wyrażenie algorytmu

const char EPSILON = '\0'; // Reprezentacja pustego przejścia

struct Edge { //Struct reprezentujący literę(letter) potrzebną do przejścia do następnego stanu(to_state)
    char letter;
    int to_state;
};

// Definicja naszego grafu
// Zbior wszystkich przejść 
// Edge to {litera, nastepny stan}
// vector<Edge> to każdy wiersz, a vector<vector<Edge>> to kolumny i wiersze (czyli całość)
const vector<vector<Edge>> nfaGraph = {
    /* S0 */ { {'A', 1}, {EPSILON, 2} },
    /* S1 */ { {EPSILON, 0} },
    /* S2 */ { {'B', 3}, {'C', 3}, {EPSILON, 4} },
    /* S3 */ { {EPSILON, 2} },
    /* S4 */ { {'A', 5} },
    /* S5 */ { {'C', 6} },
    /* S6 */ { } // Stan końcowy, brak wyjść
};

// 1. DOMKNIĘCIE EPSILONOWE
// Rekurencyjnie dodaje wszystkie stany osiągalne za darmo (bez czytania litery)
void addEpsilonClosure(int state, set<int>& current_states) {
    // Jeśli stan już jest w zbiorze, zapobiegamy nieskończonej pętli
    if (current_states.count(state)) return;
    
    current_states.insert(state);
    
    // Szukamy darmowych przejść wychodzących z tego stanu
    for (const auto& edge : nfaGraph[state]) {
        if (edge.letter == EPSILON) {
            addEpsilonClosure(edge.to_state, current_states);
        }
    }
}

// 2. PRZEJŚCIE LITEROWE
// Przeskakuje do nowych stanów na podstawie jednej litery z tekstu
set<int> moveByLetter(const set<int>& current_states, char c) {
    set<int> next_states; //Tymczasowy zbior stanow po przejsciu literowym
    
    for (int state : current_states) {// Pętla chodzaca po wszystkich aktualnych stanach szukajacą przjeść
        for (const auto& edge : nfaGraph[state]) {// Pętla chodzaca po krawędziach stanów sprawdzajacą czy litera pozwala na przejście
            if (edge.letter == c) {
                next_states.insert(edge.to_state);
            }
        }
    }
    return next_states;
}

bool matchesNFA(const string& str) {
    set<int> current_states;
    
    // Zaczynamy w S0, ale natychmiast "rozlewamy się" darmowymi przejściami
    addEpsilonClosure(0, current_states);
    
    // Główna pętla czytająca napis
    for (char c : str) {
        // Krok 1: Przechodzimy po literze
        set<int> after_letter = moveByLetter(current_states, c); // Tymczasowy set pomagający nam z przejściami
        
        // Krok 2: Od nowych stanów znów rozlewamy się darmowymi przejściami
        current_states.clear();
        for (int state : after_letter) {
            addEpsilonClosure(state, current_states);
        }
        
        // Optymalizacja: jeśli zbiór jest pusty, napis na pewno jest błędny
        if (current_states.empty()) return false;
    }
    
    // Akceptujemy, jeśli w końcowym zbiorze stanów znajduje się stan docelowy (S6)
    return current_states.count(6) > 0;
}

int main() {
    string testy[] = {
        "AC",        // DOPASOWANY (Epsilon omija A* i (B|C)*)
        "AAC",       // DOPASOWANY
        "BAC",       // DOPASOWANY
        "BCAAC",     // NIEDOPASOWANY 
        "ACAC",      // DOPASOWANY
        "AC",        // DOPASOWANY 
        "ADAC",      // NIEDOPASOWANY
        "BCBBCAC"    // DOPASOWANY 
    };

    for (const auto& s : testy) {
        cout << "\"" << s << "\" -> " 
                  << (matchesNFA(s) ? "DOPASOWANY" : "NIEDOPASOWANY") 
                  << endl;
    }

    return 0;
}