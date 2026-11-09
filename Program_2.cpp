#include <iostream>
#include <string>
#include <vector>

using namespace std;

//(A*(B|C)*AC) - wyrażenie algorytmu


const int S1 = 0; // Sekcja A*
const int S2 = 1; // Sekcja (B|C)*
const int S3 = 2; // Końcowe A
const int S4 = 3; // Końcowe C (sukces)

int charToIndex(char c) {
    if (c == 'A') return 0;
    if (c == 'B') return 1;
    if (c == 'C') return 2;
    return 3;         
}

bool matchesPattern(const string& str) {
    // Tabela przejść NFA
    // Zawiera listy stanów, do których możemy przejść.
    // Pusta lista {} oznacza brak możliwych przejść.
    const vector<int> nfaTable[4][4] = {
        /*               'A'            'B'      'C'      INNE */
        /* [0] S1 */  { {S1, S3},      {S2},    {S2},    {} },
        /* [1] S2 */  { {S3},          {S2},    {S2},    {} },
        /* [2] S3 */  { {},            {},      {S4},    {} },
        /* [3] S4 */  { {},            {},      {},      {} }
    };

    // Tablica 4 wartości true/false przechowująca informację, gdzie obecnie jesteśmy
    // Tablica superpozycji stanów
    bool current_states[4] = {true, false, false, false}; // Zaczynamy tylko w S1

    // Przechodzimy po każdej literze w napisie
    for (char ch : str) {
        // Przygotowujemy czystą tablicę na następny krok
        bool next_states[4] = {false, false, false, false};
        int col = charToIndex(ch);

        // Sprawdzamy każdy z 4 stanów
        for (int i = 0; i < 4; i++) {
            // Jeśli stan 'i' jest teraz aktywny to:
            if (current_states[i] == true) {
                // idziemy do wszystkich stanów docelowych z tabeli
                for (int docelowy_stan : nfaTable[i][col]) {
                    next_states[docelowy_stan] = true; // Zapalamy nowy stan
                }
            }
        }

        // Aktualizacja obecnych stanów
        for (int i = 0; i < 4; i++) {
            current_states[i] = next_states[i];
        }

        if (!current_states[0] && !current_states[1] && !current_states[2] && !current_states[3])
            return false; // Wszystkie ścieżki umarły, nie ma sensu czytać dalej
    }

    // Akceptujemy napis, jeśli na końcu jesteśmy w stanie docelowym S4
    return current_states[S4];
}

int main() {
    string tests[] = {
        "AAC",
        "AC",
        "BBBBC",
        "",
        "CBAC",
        "AABC"
    };

    for(const auto& s : tests){
        cout << "\"" << s <<"\" -> " 
              << (matchesPattern(s) ? "DOPASOWANY" : "NIEDOPASOWANY") << "\n";
    }
    return 0;
}