"""
DESC Cloud-Native Demo — Locust Load Test
All requests go through the API Gateway which routes to the correct microservice.

Usage:
  # Web UI (show to evaluation board)
  locust -f locustfile.py --host http://<alb-dns>
  # Open http://localhost:8089 → users=200, spawn rate=20

  # Headless
  locust -f locustfile.py --host http://<alb-dns> --headless -u 200 -r 20 --run-time 10m
"""
import random
import time
from locust import HttpUser, task, between, events


class GatewayUser(HttpUser):
    """Simulates a citizen using the portal — all calls routed via the API Gateway."""
    wait_time = between(0.1, 0.5)

    @task(5)
    def stress_records_service(self):
        """Triggers CPU load on Records Service → drives HPA scaling."""
        with self.client.get(
            "/api/stress",
            params={"n": random.randint(6000, 10000)},
            catch_response=True, timeout=30, name="/api/stress → records-svc"
        ) as r:
            if r.status_code == 200 and "primes_found" in r.text:
                r.success()
            else:
                r.failure(f"HTTP {r.status_code}")

    @task(3)
    def list_records(self):
        with self.client.get(
            "/api/records", catch_response=True, name="/api/records (GET)"
        ) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"HTTP {r.status_code}")

    @task(2)
    def list_users(self):
        with self.client.get(
            "/api/users", catch_response=True, name="/api/users (GET)"
        ) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"HTTP {r.status_code}")

    @task(2)
    def create_record(self):
        payload = {
            "title": f"Locust record {int(time.time())}",
            "description": "Created by Locust load test",
            "status": "pending",
        }
        with self.client.post(
            "/api/records", json=payload, catch_response=True, name="/api/records (POST)"
        ) as r:
            if r.status_code == 201:
                r.success()
            else:
                r.failure(f"HTTP {r.status_code}")

    @task(1)
    def list_notifications(self):
        with self.client.get(
            "/api/notifications", catch_response=True, name="/api/notifications (GET)"
        ) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"HTTP {r.status_code}")

    @task(1)
    def aggregate_health(self):
        """Exercises gateway fan-out health check."""
        with self.client.get(
            "/api/health", catch_response=True, name="/api/health (gateway fan-out)"
        ) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"HTTP {r.status_code}")


@events.test_start.add_listener
def on_start(environment, **kwargs):
    print("=" * 60)
    print(" DESC Microservices Load Test — via API Gateway")
    print(" Watch HPA: kubectl get hpa -n desc-app -w")
    print("=" * 60)


@events.test_stop.add_listener
def on_stop(environment, **kwargs):
    stats = environment.runner.stats.total
    print("\n" + "=" * 60)
    print(f" Requests  : {stats.num_requests}")
    print(f" Failures  : {stats.num_failures}")
    print(f" Avg (ms)  : {stats.avg_response_time:.0f}")
    print(f" P95 (ms)  : {stats.get_response_time_percentile(0.95):.0f}")
    print("=" * 60)
