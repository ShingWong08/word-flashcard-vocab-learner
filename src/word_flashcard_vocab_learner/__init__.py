"""A lightweight CLI flashcard tool for vocabulary learning and review."""

__version__ = "0.1.2"


def main() -> None:
    import os

    import requests

    from .chatColor import ChatColor as C
    from .connectFreeDictionaryAPI import formatWordDefinition, getWordDefinition

    print(C.paint("Welcome to the Word Flashcard Vocab Learner!", C.BOLD, C.CYAN))
    print("This package helps you learn English vocabulary more easily!")
    print(C.paint("Type an English word to look it up, or 'q' to quit.\n", C.DARK_GRAY))

    while True:
        try:
            word = input(C.paint("Word: ", C.BOLD, C.YELLOW)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if word.lower() in ("q", "quit", "exit"):
            break
        if not word:
            continue

        try:
            result = getWordDefinition(word)
        except requests.RequestException as error:
            print(C.paint(f"Could not reach the dictionary: {error}\n", C.RED))
            continue

        print(formatWordDefinition(result))

        if result["definitions"] and os.environ.get("ELEVENLABS_API_KEY"):
            answer = input(C.paint("Play pronunciation? (y/N) ", C.YELLOW)).strip().lower()
            if answer in ("y", "yes"):
                try:
                    from .textToSpeech import textToSpeech
                    textToSpeech(word)
                except ImportError:
                    print(C.paint("Speech support is not installed. Run: pip install .[speech]", C.ORANGE))
                except Exception as error:
                    print(C.paint(f"Could not play pronunciation: {error}", C.RED))
        print()

    print(C.paint("Goodbye!", C.BOLD, C.CYAN))


if __name__ == "__main__":
    main()
