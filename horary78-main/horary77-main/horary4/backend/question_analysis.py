# -*- coding: utf-8 -*-
"""Question analysis utilities for horary astrology engine."""

from typing import Dict, Any, List, Optional, Set

class TraditionalHoraryQuestionAnalyzer:
    """Analyze questions using traditional horary house assignments"""
    
    def __init__(self):
        # Traditional house meanings for horary
        self.house_meanings = {
            1: ["querent", "self", "body", "life", "personality", "appearance"],
            2: ["money", "possessions", "moveable goods", "income", "resources", "values"],
            3: ["siblings", "neighbors", "short journeys", "communication", "letters", "rumors"],
            4: ["father", "home", "land", "property", "endings", "foundations", "graves"],
            5: ["children", "pregnancy", "pleasure", "gambling", "creativity", "entertainment"],
            6: ["illness", "servants", "small animals", "work", "daily routine", "uncle/aunt"],
            7: ["spouse", "partner", "open enemies", "thieves", "others", "contracts"],
            8: ["death", "partner's money", "wills", "transformation", "fear", "surgery"],
            9: ["long journeys", "foreign lands", "religion", "law", "higher learning", "dreams"],
            10: ["mother", "career", "honor", "reputation", "authority", "government"],
            11: ["friends", "hopes", "wishes", "advisors", "king's money", "groups"],
            12: ["hidden enemies", "large animals", "prisons", "secrets", "self-undoing", "witchcraft"]
        }
        
        # Question type patterns
        self.question_patterns = {
            "lost_object": ["where is", "lost", "missing", "find", "stolen"],
            "marriage": ["marry", "wedding", "spouse", "husband", "wife"],
            "pregnancy": ["pregnant", "child", "baby", "conceive"],
            "travel": ["journey", "travel", "trip", "go to", "visit"],
            "money": ["money", "wealth", "rich", "profit", "gain", "debt"],
            "career": ["job", "career", "work", "employment", "business"],
            "health": ["sick", "illness", "disease", "health", "recover", "die"],
            "lawsuit": ["court", "lawsuit", "legal", "judge", "trial"],
            "relationship": ["love", "relationship", "friend", "enemy"]
        }
        
        # Person keywords mapped to their traditional houses
        self.person_keywords = {
            4: ["father", "dad", "grandfather", "stepfather"],
            10: ["mother", "mom", "mum", "stepmother"],
            7: ["spouse", "husband", "wife", "partner"],
            3: ["brother", "sister", "sibling"],
            5: ["child", "son", "daughter", "baby"],
            11: ["friend", "ally", "benefactor"]
        }
    
    def _turn(self, base: int, offset: int) -> int:
        """Return the house offset steps from base (1-based)."""
        return ((base + offset - 1) % 12) + 1
    
    def analyze_question(self, question: str) -> Dict[str, Any]:
        """Analyze question to determine significators using traditional methods"""
        
        question_lower = question.lower()
        
        # Determine question type
        question_type = self._determine_question_type(question_lower)
        
        # Determine primary houses involved
        houses = self._determine_houses(question, question_type)
        
        # Determine significators
        significators = self._determine_significators(houses, question_type)
        
        return {
            "question_type": question_type,
            "relevant_houses": houses,
            "significators": significators,
            "traditional_analysis": True
        }
    
    def _determine_question_type(self, question: str) -> str:
        """Determine the type of horary question"""
        for q_type, keywords in self.question_patterns.items():
            if any(keyword in question for keyword in keywords):
                return q_type
        return "general"
    
    def _determine_houses(self, question: str, question_type: str) -> List[int]:
        """Determine which houses are involved in the question"""
        from typing import List, Set, Optional
        question_lower = question.lower()
        houses: List[int] = [1]  # 1st house = querent
        
        # ------------- detect named person -------------
        subject_house: Optional[int] = None
        for h, kws in self.person_keywords.items():
            if any(k in question_lower for k in kws):
                subject_house = h
                break
        
        # ------------- detect key themes ---------------
        death_words = ["die", "death", "pass away", "funeral"]
        illness_words = ["sick", "illness", "disease", "recover"]
        
        if subject_house is not None:
            if any(w in question_lower for w in death_words):
                houses.append(self._turn(subject_house, 8))  # 8th from subject
                houses.append(subject_house)
            elif any(w in question_lower for w in illness_words):
                houses.append(self._turn(subject_house, 6))  # 6th from subject
                houses.append(subject_house)
            else:
                houses.append(subject_house)
        else:
            # ✱ Unchanged fallback branch ✱
            if question_type == "lost_object":
                houses.append(2)  # Moveable possessions
            elif question_type == "marriage" or "spouse" in question_lower:
                houses.append(7)  # Marriage/spouse
            elif question_type == "pregnancy" or "child" in question_lower:
                houses.append(5)  # Children
            elif question_type == "travel":
                if any(word in question_lower for word in ["far", "foreign", "abroad"]):
                    houses.append(9)  # Long journeys
                else:
                    houses.append(3)  # Short journeys
            elif question_type == "money":
                houses.append(2)  # Money/possessions
            elif question_type == "career":
                houses.append(10)  # Career/reputation
            elif question_type == "health":
                houses.append(6)  # Illness
            elif question_type == "lawsuit":
                houses.append(7)  # Open enemies/legal opponents
            else:
                # Default to 7th house for "others" or general questions
                houses.append(7)

            # Look for specific house keywords
            for house, keywords in self.house_meanings.items():
                if house not in houses and any(keyword in question_lower for keyword in keywords):
                    houses.append(house)
        
        # ------------- de-duplicate while preserving order -------------
        seen: Set[int] = set()
        return [h for h in houses if not (h in seen or seen.add(h))]
    
    def _determine_significators(self, houses: List[int], question_type: str) -> Dict[str, Any]:
        """Determine traditional significators"""
        
        significators = {
            "querent_house": 1,  # Always 1st house
            "quesited_house": houses[1] if len(houses) > 1 else 7,
            "moon_role": "co-significator of querent and general flow",
            "special_significators": {}
        }
        
        # Add natural significators based on question type
        if question_type == "marriage":
            significators["special_significators"]["venus"] = "natural significator of love"
            significators["special_significators"]["mars"] = "natural significator of men"
        elif question_type == "money":
            significators["special_significators"]["jupiter"] = "greater fortune"
            significators["special_significators"]["venus"] = "lesser fortune"
        elif question_type == "career":
            significators["special_significators"]["sun"] = "honor and reputation"
            significators["special_significators"]["jupiter"] = "success"
        elif question_type == "health":
            significators["special_significators"]["mars"] = "fever and inflammation"
            significators["special_significators"]["saturn"] = "chronic illness"
        
        return significators


