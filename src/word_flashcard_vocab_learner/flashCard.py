from dataclasses import asdict, dataclass, field
from datetime import date


def todayISO() -> str:
    """
    Return today's date as an ISO string, e.g. "2026-11-18".
    """

    return date.today().isoformat()


def _asCount(value: object) -> int:
    """
    Turn a counter loaded from a deck file into a whole number.
    A value that is missing, null or not a number counts as 0, so a hand-edited deck
    cannot break the screens.
    """

    if isinstance(value, bool):
        return 0

    if isinstance(value, (int, float)):
        return max(0, int(value))

    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return max(0, int(value.strip()))

    return 0


def _asBox(value: object) -> int:
    """
    Turn the Leitner box loaded from a deck file into 1-5.
    """

    return min(5, max(1, _asCount(value)))


def _asDate(value: object) -> str:
    """
    Return an ISO date loaded from a deck file, or today when it is missing or not a
    date.
    """

    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()).isoformat()
        except ValueError:
            pass

    return todayISO()


@dataclass
class Card:
    """
    One flashcard: an English word on the front, its meaning on the back,
    plus the Leitner box and next review date used for spaced repetition.

    Fields:
        - word (str): The English word (the spelling the dictionary matched).
        - definitions (list[str]): English definitions from the dictionary.
        - examples (list[list[str]]): examples[i] holds the example sentences of
          definitions[i].
        - translation (str): Chinese translation, filled by the AI tutor when available.
        - box (int): Leitner box from 1 (new / forgotten) to 5 (well known).
        - nextReview (str): ISO date when the card is due again.
        - correctCount (int): How many reviews were answered correctly.
        - wrongCount (int): How many reviews were answered wrongly.
        - addedOn (str): ISO date when the card was added.
    """

    word: str
    definitions: list[str]
    examples: list[list[str]] = field(default_factory=list)
    translation: str = ""
    box: int = 1
    nextReview: str = field(default_factory=todayISO)
    correctCount: int = 0
    wrongCount: int = 0
    addedOn: str = field(default_factory=todayISO)

    @classmethod
    def fromLookup(cls, result: dict, translation: str = "") -> "Card":
        """
        Create a new card from the dict returned by getWordDefinition.
        A new card starts in box 1 and is due today.
        """

        return cls(
            word=result["word"],
            definitions=list(result["definitions"]),
            examples=[list(eachExamples) for eachExamples in result["examples"]],
            translation=translation,
        )

    @classmethod
    def fromDict(cls, data: dict) -> "Card":
        """
        Create a card from a dict loaded from the deck file.
        Unknown keys are ignored, so older or newer deck files still load,
        and a hand-edited value of the wrong type or a missing value is repaired
        instead of breaking the screens later.
        Raises ValueError when the entry has no word at all.
        """

        if not isinstance(data, dict):
            raise ValueError("one entry of the deck file is not a card")

        word = data.get("word")
        if not isinstance(word, str) or not word.strip():
            raise ValueError("one card of the deck file has no word")

        definitions = data.get("definitions")
        examples = data.get("examples")
        translation = data.get("translation")

        if isinstance(examples, list):
            examples = [
                (
                    [str(eachLine) for eachLine in eachExample]
                    if isinstance(eachExample, list)
                    else []
                )
                for eachExample in examples
            ]
        else:
            examples = []

        return cls(
            word=word.strip(),
            definitions=(
                [str(each) for each in definitions]
                if isinstance(definitions, list)
                else []
            ),
            examples=examples,
            translation=translation if isinstance(translation, str) else "",
            box=_asBox(data.get("box")),
            nextReview=_asDate(data.get("nextReview")),
            correctCount=_asCount(data.get("correctCount")),
            wrongCount=_asCount(data.get("wrongCount")),
            addedOn=_asDate(data.get("addedOn")),
        )

    def toDict(self) -> dict:
        """
        Return the card as a plain dict that can be saved as JSON.
        """

        return asdict(self)

    def timesReviewed(self) -> int:
        return self.correctCount + self.wrongCount
