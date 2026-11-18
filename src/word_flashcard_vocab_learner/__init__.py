"""A lightweight CLI flashcard tool for vocabulary learning and review."""

__version__ = "0.1.2"


def main() -> None:
    import os

    import requests

    from .connectFreeDictionaryAPI import formatWordDefinition, getWordDefinition

    print("Welcome to the Word Flashcard Vocab Learner!")
    print("This package helps you learn English vocabulary more easily!")
    print("Type an English word to look it up, or 'q' to quit.\n")

    while True:
        try:
            word = input("Word: ").strip()
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
            print(f"Could not reach the dictionary: {error}\n")
            continue

        print(formatWordDefinition(result))

        if result["definitions"] and os.environ.get("ELEVENLABS_API_KEY"):
            answer = input("Play pronunciation? (y/N) ").strip().lower()
            if answer in ("y", "yes"):
                try:
                    from .textToSpeech import textToSpeech
                    textToSpeech(word)
                except ImportError:
                    print("Speech support is not installed. Run: pip install .[speech]")
                except Exception as error:
                    print(f"Could not play pronunciation: {error}")
        print()

    print("Goodbye!")


if __name__ == "__main__":
    main()
