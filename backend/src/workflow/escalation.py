class EscalationPolicy:
    HARD_ESCALATION_CATEGORIES = {"security_incident", "hardware_failure", "network_outage"}
    
    @classmethod
    def should_escalate(cls, state: dict) -> bool:
        # If AI explicitly flags escalate
        if state.get("escalate") is True:
            return True
            
        category = state.get("category")
        if category in cls.HARD_ESCALATION_CATEGORIES:
            return True
            
        # Error thresholds, etc.
        errors = [e for e in state.get("evidence", []) if "error" in e]
        if len(errors) >= 2:
            return True
            
        return False
