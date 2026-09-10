class EscalationPolicy:
    HARD_ESCALATION_CATEGORIES = {"security_incident", "hardware_failure", "datacenter_outage"}

    
    @classmethod
    def should_escalate(cls, state: dict) -> bool:
        # If AI explicitly flags escalate or needs_handoff
        if state.get("escalate") is True or state.get("needs_handoff") is True:
            return True
            
        category = state.get("category")
        if category in cls.HARD_ESCALATION_CATEGORIES:
            return True
            
        # Error thresholds, etc.
        errors = [e for e in state.get("evidence", []) if isinstance(e, dict) and "error" in e]
        if len(errors) >= 2:
            return True
            
        return False

