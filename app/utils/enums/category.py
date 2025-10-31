from enum import Enum

class Category(str, Enum):
    GENERAL = "general"
    LOVE = "love"
    FAMILY = "family"
    CAREER = "career"
    WEALTH = "wealth"
    HEALTH = "health"
    PERSONALITY = "personality"
    EDUCATION = "education"
    TRAVEL_AND_RELOCATION = "travel_and_relocation"
    MENTAL_WELLBEING = "mental_wellbeing"