from dataclasses import asdict, dataclass, field, fields
from datetime import date


def todayISO() -> str:

    """
    Return today's date as an ISO string, e.g. "2026-11-18".
    """

    return date.today().isoformat()


@dataclass
class Card:

    """
    One flashcard: an English word on the front, its meaning on the back,
    plus the Leitner box and next review date used for spaced repetition.

    Fields:
        - word (str): The English word (the spelling the dictionary matched).
        - definitions (list[str]): English definitions from the dictionary.
        - examples (list[list[str]]): examples[i] holds the example sentences of definitions[i].
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

        examples = []
        for eachExampleList in result["examples"]:
            examples.append(list(eachExampleList))

        return cls(
            word=result["word"],
            definitions=list(result["definitions"]),
            examples=examples,
            translation=translation,
        )

    @classmethod
    def fromDict(cls, data: dict) -> "Card":

        """
        Create a card from a dict loaded from the deck file.
        Unknown keys are ignored, so older or newer deck files still load.
        """

        knownFields = []
        for eachField in fields(cls):
            knownFields.append(eachField.name)

        values = {}
        for key, value in data.items():
            if key in knownFields:
                values[key] = value

        return cls(**values)

    def toDict(self) -> dict:

        """
        Return the card as a plain dict that can be saved as JSON.
        """

        return asdict(self)

    def timesReviewed(self) -> int:
        return self.correctCount + self.wrongCount
