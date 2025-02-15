from typing import Literal, TypedDict


type DataType = Literal["comic", "original"]


class AnalyzedData(TypedDict):
    id: str
    name: str
    type: DataType
