#include <iostream>
#include <string>
using namespace std;

//A*(B|C)*B

enum State {
    S0 = 0,
    S1 = 1,
    S2 = 2,
    TRAP = 3
};

int charToIndex(char c) {
    switch (c) {
        case 'A': return 0;
        case 'B': return 1;
        case 'C': return 2;
        default:  return 3;
    }
}

bool matchesPatternTable(const string& str) {
    const State transitionTable[4][4] = {
        /*          A      B      C      INNE */
        /* S0 */  { S0,    S1,    S2,    TRAP },
        /* S1 */  { TRAP,  S1,    S2,    TRAP },
        /* S2 */  { TRAP,  S1,    S2,    TRAP },
        /* TRAP*/ { TRAP,  TRAP,  TRAP,  TRAP }
    };

    State currentState = S0;

    for (char ch : str) {
        currentState = transitionTable[currentState][charToIndex(ch)];
        
        if (currentState == TRAP) {
            return false;
        }
    }

    // Akceptujemy tylko, jeśli skończyliśmy w stanie S1
    return currentState == S1;
}

int main() {
    string testy[] = {
        "B",        // TAK (S0 -> S1)
        "AAAB",     // TAK (S0 -> S0 -> S0 -> S0 -> S1)
        "ABCB",     // TAK (S0 -> S0 -> S1 -> S2 -> S1)
        "ACCCCB",   // TAK (S0 -> S0 -> S2 -> S2 -> S2 -> S2 -> S1)
        "",         // NIE (S0 - nieakceptujący)
        "ABC",      // NIE (kończy w S2)
        "BACB",      // NIE (S0 -> S1 -> TRAP -> ...)
        "ABAB",     // NIE (kończy w S1, ale nieakceptujący)
    };

    for (const auto& s : testy) {
        std::cout << "\"" << s << "\" -> " 
                  << (matchesPatternTable(s) ? "DOPASOWANY" : "NIEDOPASOWANY") 
                  << std::endl;
    }

    return 0;
}