"""
Date utility functions
"""
from datetime import datetime, timedelta


def calculate_trial_end_date(start_date: datetime, days: int = 14) -> datetime:
    """
    Calculate trial end date from a start date
    
    Args:
        start_date: The start date for the trial period
        days: Number of days for the trial period (default: 14)
        
    Returns:
        datetime: Trial end date
    """
    return start_date + timedelta(days=days)


def is_trial_expired(trial_end_date: datetime) -> bool:
    """
    Check if trial period has expired
    
    Args:
        trial_end_date: The trial end date to check
        
    Returns:
        bool: True if trial has expired, False otherwise
    """
    return datetime.utcnow() > trial_end_date