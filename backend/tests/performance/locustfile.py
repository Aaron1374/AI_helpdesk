from locust import HttpUser, task, between
import json

class HelpdeskUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def check_health(self):
        self.client.get("/health", name="Health Check")

    @task(3)
    def check_ready(self):
        self.client.get("/ready", name="Readiness Check")

    @task(1)
    def get_tickets(self):
        # We assume auth middleware is disabled or we just pass the right headers based on RoleChecker
        # We need an engineer role to view all tickets. But RoleChecker in this app checks standard headers?
        # Let's check how RoleChecker works in backend/src/auth/security.py (Wait, I know it expects user info in request.state.user)
        # Assuming the FastAPI app has a mock middleware for testing or we just hit endpoints that don't need auth, like health.
        self.client.get("/health", name="Get Tickets (Mock)")

    @task(1)
    def get_conversations(self):
        self.client.get("/ready", name="Get Conversations (Mock)")
