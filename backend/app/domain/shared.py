from enum import Enum


class TargetKind(str, Enum):
    SENSE = "sense"
    FORM = "form"
    CONSTRUCTION = "construction"


class Capability(str, Enum):
    RECOGNIZE_MEANING = "recognize_meaning"
    RETRIEVE_FORM = "retrieve_form"
    APPLY_CONSTRUCTION = "apply_construction"


class Modality(str, Enum):
    WRITTEN = "written"
