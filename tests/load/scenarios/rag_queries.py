"""
RAG Queries Scenario

This scenario simulates users interacting with the RAG (Retrieval-Augmented Generation)
chat system, asking questions about tenders, analytics, and insights.
"""

import random
from locust import task, TaskSet


class RAGQueriesScenario(TaskSet):
    """
    Realistic RAG chat interaction behavior.
    Users typically:
    1. Login to access RAG features
    2. Ask questions about tenders
    3. Request analytics and insights
    4. Follow up with related questions
    5. Provide context from specific tenders
    """

    RAG_QUERIES = [
        # General analytics queries
        "Katere so največje javne naročilnice v zadnjem letu?",
        "Pokaži trende v IT naročilih",
        "Kdo so najpogostejši dobavitelji?",
        "Kakšna je povprečna vrednost naročil za medicino?",
        "Prikaži statistiko po regijah",

        # Specific analysis queries
        "Kateri postopki so najpogostejši?",
        "Kako se je trg spremenil zadnjih 6 mesecev?",
        "Prikaži anomalije v cenah",
        "Katere institucije izdajo največ naročil?",
        "Analiziraj konkurenco v gradbeništvu",

        # Trend analysis
        "Kakšni so trendi v javnih naročilih za IT opremo?",
        "Prikaži sezončnost v gradbenih naročilih",
        "Kako se spreminjajo povprečne cene v zdravstvu?",

        # Comparative queries
        "Primerjaj naročila med regijami",
        "Katera ministrstva porabijo največ?",
        "Primerjaj cene med različnimi dobavitelji",

        # Predictive queries
        "Predvidi trende za naslednje četrtletje",
        "Katera področja bodo imela največ naročil?",

        # Specific domain queries
        "Analiziraj medicinska naročila zadnjega leta",
        "Pokaži vse IT projekte nad 100.000 EUR",
        "Katere so največje gradbene investicije?",
        "Seznam vseh naročil za čistilne storitve",

        # Supplier queries
        "Kdo dobavlja največ pisarniške opreme?",
        "Seznam dobaviteljev za medicinske pripomočke",
        "Kateri dobavitelji imajo najbolj konkurenčne cene?",
    ]

    FOLLOW_UP_QUERIES = [
        "Razloži podrobneje",
        "Pokaži še podatke za preteklo leto",
        "Kakšni so razlogi za ta trend?",
        "Ali imaš kakšne priporočila?",
        "Primerjaj s preteklim letom",
    ]

    CONTEXT_QUERIES = [
        "Analiziraj to naročilo",
        "Primerjaj cene s podobnimi naročili",
        "Kdo so konkurenti za to naročilo?",
        "Ali je cena primerna?",
        "Pokaži podobna naročila",
    ]

    def on_start(self):
        """Initialize RAG scenario with login"""
        self.user_id = random.randint(1, 1000)
        self.email = f"test_user_{self.user_id}@example.com"
        self.token = None
        self.conversation_history = []
        self.current_tender_context = None
        self.login()

    def login(self):
        """Authenticate user"""
        payload = {
            "email": self.email,
            "password": "test_password_123"
        }

        response = self.client.post(
            "/api/v1/auth/login",
            json=payload,
            name="/api/v1/auth/login (RAG)"
        )

        if response.status_code == 200:
            try:
                data = response.json()
                self.token = data.get("access_token")
            except:
                self.token = None

    def get_auth_headers(self):
        """Get authorization headers"""
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    @task(30)
    def ask_general_question(self):
        """Ask general analytics question"""
        if not self.token:
            self.login()

        query = random.choice(self.RAG_QUERIES)
        payload = {
            "query": query
        }

        with self.client.post(
            "/api/v1/rag/query",
            json=payload,
            headers=self.get_auth_headers(),
            name="/api/v1/rag/query (general)",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "answer" in data or "response" in data:
                        self.conversation_history.append({
                            "query": query,
                            "response": data
                        })
                        response.success()
                    else:
                        response.failure("Missing answer in response")
                except Exception as e:
                    response.failure(f"Parse error: {str(e)}")
            elif response.status_code == 401:
                self.login()
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(15)
    def ask_followup_question(self):
        """Ask follow-up question based on conversation history"""
        if not self.token:
            self.login()

        if not self.conversation_history:
            # Ask initial question first
            self.ask_general_question()
            return

        followup = random.choice(self.FOLLOW_UP_QUERIES)
        payload = {
            "query": followup,
            "conversation_id": f"conv_{self.user_id}"
        }

        with self.client.post(
            "/api/v1/rag/query",
            json=payload,
            headers=self.get_auth_headers(),
            name="/api/v1/rag/query (followup)",
            catch_response=True
        ) as response:
            if response.status_code in [200, 401]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(20)
    def query_with_tender_context(self):
        """Ask question with specific tender context"""
        if not self.token:
            self.login()

        tender_id = random.randint(1, 1000)
        query = random.choice(self.CONTEXT_QUERIES)

        payload = {
            "query": query,
            "context": {
                "tender_id": tender_id,
                "type": "tender_analysis"
            }
        }

        with self.client.post(
            "/api/v1/rag/query",
            json=payload,
            headers=self.get_auth_headers(),
            name="/api/v1/rag/query (with context)",
            catch_response=True
        ) as response:
            if response.status_code in [200, 401]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(10)
    def get_conversation_history(self):
        """Retrieve conversation history"""
        if not self.token:
            self.login()

        with self.client.get(
            "/api/v1/rag/conversations",
            headers=self.get_auth_headers(),
            name="/api/v1/rag/conversations",
            catch_response=True
        ) as response:
            if response.status_code in [200, 401, 404]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(8)
    def get_suggested_questions(self):
        """Get suggested questions based on current context"""
        if not self.token:
            self.login()

        params = {}
        if self.current_tender_context:
            params["tender_id"] = self.current_tender_context

        with self.client.get(
            "/api/v1/rag/suggestions",
            params=params,
            headers=self.get_auth_headers(),
            name="/api/v1/rag/suggestions",
            catch_response=True
        ) as response:
            if response.status_code in [200, 401, 404]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(5)
    def rate_response(self):
        """Rate RAG response quality"""
        if not self.token:
            self.login()

        if not self.conversation_history:
            return

        response_id = f"resp_{random.randint(1, 10000)}"
        rating = random.choice([1, 2, 3, 4, 5])

        payload = {
            "response_id": response_id,
            "rating": rating,
            "feedback": random.choice([
                "Helpful answer",
                "Could be more detailed",
                "Good insights",
                None
            ])
        }

        with self.client.post(
            "/api/v1/rag/feedback",
            json=payload,
            headers=self.get_auth_headers(),
            name="/api/v1/rag/feedback",
            catch_response=True
        ) as response:
            if response.status_code in [200, 201, 401, 404]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(7)
    def export_conversation(self):
        """Export conversation to PDF/text"""
        if not self.token:
            self.login()

        conversation_id = f"conv_{self.user_id}"
        format_type = random.choice(["pdf", "txt", "json"])

        with self.client.get(
            f"/api/v1/rag/conversations/{conversation_id}/export",
            params={"format": format_type},
            headers=self.get_auth_headers(),
            name="/api/v1/rag/conversations/[id]/export",
            catch_response=True
        ) as response:
            if response.status_code in [200, 401, 404]:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(3)
    def clear_conversation(self):
        """Clear/delete conversation history"""
        if not self.token:
            self.login()

        conversation_id = f"conv_{self.user_id}"

        with self.client.delete(
            f"/api/v1/rag/conversations/{conversation_id}",
            headers=self.get_auth_headers(),
            name="/api/v1/rag/conversations/[id] (delete)",
            catch_response=True
        ) as response:
            if response.status_code in [200, 204, 401, 404]:
                self.conversation_history = []
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
