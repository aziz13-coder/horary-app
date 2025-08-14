import sys
from pathlib import Path

# Add backend module path for importing TraditionalHoraryQuestionAnalyzer
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "horary78-main" / "horary77-main" / "horary4" / "backend"))

from question_analysis import TraditionalHoraryQuestionAnalyzer

analyzer = TraditionalHoraryQuestionAnalyzer()

def test_lost_item_analysis():
    result = analyzer.analyze_question("Where is my ring?")
    assert result["question_type"] == "lost_object"
    assert result["relevant_houses"] == [1, 2]
    assert result["significators"] == {
        "querent_house": 1,
        "quesited_house": 2,
        "moon_role": "co-significator of querent and general flow",
        "special_significators": {},
    }

def test_marriage_analysis():
    result = analyzer.analyze_question("Will I marry soon?")
    assert result["question_type"] == "marriage"
    assert result["relevant_houses"] == [1, 7]
    assert result["significators"] == {
        "querent_house": 1,
        "quesited_house": 7,
        "moon_role": "co-significator of querent and general flow",
        "special_significators": {
            "venus": "natural significator of love",
            "mars": "natural significator of men",
        },
    }

def test_ill_relative_analysis():
    result = analyzer.analyze_question("Is my father ill?")
    assert result["question_type"] == "health"
    assert result["relevant_houses"] == [1, 6, 4]
    assert result["significators"] == {
        "querent_house": 1,
        "quesited_house": 6,
        "moon_role": "co-significator of querent and general flow",
        "special_significators": {
            "mars": "fever and inflammation",
            "saturn": "chronic illness",
        },
    }
