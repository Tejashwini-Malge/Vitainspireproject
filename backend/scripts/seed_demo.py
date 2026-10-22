"""Local demo data for understanding the platform. Never run against a shared database.

Creates fictional NGOs, donors and donations through the real API -- the same endpoints a
browser would call -- so every business rule (verification gate, publish blockers, append-only
donations) runs exactly as it does for a real user. The one exception is granting the platform
admin, which (correctly) has no API route; this script calls the same CLI function the README
tells an operator to run.

Usage (from backend/, with the API already running):
    python scripts/seed_demo.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.cli import grant_platform_admin  # noqa: E402
from app.config import settings  # noqa: E402

API = "http://127.0.0.1:8000"
PASSWORD = "demo-seed-password"


def _refuse_unless_dev_database() -> None:
    url = settings.database_url
    if not url.endswith("/vitainspire_dev"):
        sys.exit(f"Refusing to seed: VITA_DATABASE_URL is {url!r}, expected it to end with /vitainspire_dev")


client = httpx.Client(base_url=API, timeout=10.0)


def register(email: str, name: str) -> None:
    r = client.post("/auth/register", json={"email": email, "password": PASSWORD, "full_name": name})
    if r.status_code not in (201, 409):
        sys.exit(f"register {email} failed: {r.status_code} {r.text}")


def login(email: str) -> str:
    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    r.raise_for_status()
    return r.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def create_org(token: str, name: str, org_type: str) -> str:
    r = client.post("/orgs", json={"name": name, "org_type": org_type}, headers=auth(token))
    r.raise_for_status()
    return r.json()["id"]


def set_profile(token: str, org_id: str, **profile) -> None:
    r = client.put(f"/orgs/{org_id}/profile", json=profile, headers=auth(token))
    r.raise_for_status()


def publish_profile(token: str, org_id: str) -> None:
    client.post(f"/orgs/{org_id}/profile/publish", headers=auth(token)).raise_for_status()


def create_project(token: str, org_id: str, title: str, summary: str, description: str) -> str:
    r = client.post(
        f"/orgs/{org_id}/projects",
        json={"title": title, "summary": summary, "description": description},
        headers=auth(token),
    )
    r.raise_for_status()
    return r.json()["id"]


def publish_project(token: str, org_id: str, project_id: str) -> None:
    client.post(f"/orgs/{org_id}/projects/{project_id}/publish", headers=auth(token)).raise_for_status()


def decide(admin_token: str, org_id: str, decision: str, reason: str | None = None) -> None:
    r = client.post(
        f"/admin/organizations/{org_id}/verification",
        json={"decision": decision, "reason": reason},
        headers=auth(admin_token),
    )
    r.raise_for_status()


def donate(org_id: str, amount: str, donor_name: str, donor_email: str, city: str, state: str, token: str | None = None, project_id: str | None = None, message: str | None = None) -> None:
    payload = {
        "donor_name": donor_name,
        "donor_email": donor_email,
        "amount": amount,
        "billing_address": {"line1": "12 Residency Road", "city": city, "state": state, "postal_code": "500001", "country": "India"},
        "project_id": project_id,
        "message": message,
    }
    r = client.post(f"/public/ngos/{org_id}/donations", json=payload, headers=auth(token) if token else {})
    r.raise_for_status()


def main() -> None:
    _refuse_unless_dev_database()

    # Platform reviewer. Granted the same way the README tells a real operator to.
    register("reviewer@imparency.org", "Imparency Reviewer")
    grant_platform_admin("reviewer@imparency.org")
    admin_token = login("reviewer@imparency.org")

    # 1. A verified NGO with a published project -- the full "give to one specific thing" path.
    register("owner@sahyoga.org", "Meera Nair")
    t1 = login("owner@sahyoga.org")
    sahyoga = create_org(t1, "Sahyoga Rural Trust", "NGO")
    set_profile(
        t1, sahyoga,
        mission="We rebuild hand-dug wells in drought-hit villages of Bundelkhand so families stop walking four kilometres for water that still makes children sick.",
        about="Started in 2014 by three schoolteachers after a well collapse in Chhatarpur district. We now maintain 42 wells across 11 villages, with a local caretaker paid to check each one monthly.",
        sectors=["Water", "Rural infrastructure"], geographies=["Bundelkhand, Madhya Pradesh"],
        founded_year=2014, website="https://example-sahyoga.org",
    )
    decide(admin_token, sahyoga, "APPROVED")
    publish_profile(t1, sahyoga)
    well_project = create_project(
        t1, sahyoga,
        "Recharge the Kharwai well before the next dry season",
        "The well 9 families in Kharwai rely on drops below usable level every March. We need to deepen it by 6 metres before then.",
        "Local caretaker Rampyari Devi flagged falling yields in January. A hydro-geologist survey (attached to our records) confirms deepening is viable at this site.",
    )
    publish_project(t1, sahyoga, well_project)

    # 2. A verified NGO with a different kind of project -- shows the feed isn't just "water".
    register("owner@udaan.org", "Kabir Oza")
    t2 = login("owner@udaan.org")
    udaan = create_org(t2, "Udaan Learning Collective", "NGO")
    set_profile(
        t2, udaan,
        mission="Evening study rooms for children in Mumbai's informal settlements, run by trained volunteers from the same neighbourhoods.",
        about="Founded in 2018 after a survey found most children in Govandi had nowhere quiet to do homework after dark. We now run 6 study rooms, each open 4 hours a night.",
        sectors=["Education"], geographies=["Govandi, Mumbai"], founded_year=2018,
    )
    decide(admin_token, udaan, "APPROVED")
    publish_profile(t2, udaan)
    roof_project = create_project(
        t2, udaan,
        "Replace the leaking roof at the Govandi study room before monsoon",
        "Rain comes through the east wall onto the one shelf of books we have. Twenty-two children study there most evenings.",
        "A local contractor (quote on file) will reroof and add a gutter for roughly this amount -- cheaper than losing the books a second year running.",
    )
    publish_project(t2, udaan, roof_project)

    # 3. A verified NGO with no project at all -- proves donating never requires one.
    register("owner@aadhar-eldercare.org", "Savitri Pillai")
    t3 = login("owner@aadhar-eldercare.org")
    aadhar = create_org(t3, "Aadhar Elder Care Society", "NGO")
    set_profile(
        t3, aadhar,
        mission="Daily hot meals and a twice-weekly health check for elders living alone in Thiruvananthapuram.",
        sectors=["Elder care"], geographies=["Thiruvananthapuram, Kerala"], founded_year=2011,
    )
    decide(admin_token, aadhar, "APPROVED")
    publish_profile(t3, aadhar)

    # 4. Still pending -- what the admin queue actually looks like day to day.
    register("owner@nirmaljal.org", "Devendra Kushwaha")
    t4 = login("owner@nirmaljal.org")
    create_org(t4, "Nirmal Jal Seva", "NGO")

    # 5. Rejected, with a stated reason -- the organization-facing side of a real decision.
    register("owner@shaktirural.org", "Pooja Thakur")
    t5 = login("owner@shaktirural.org")
    shakti = create_org(t5, "Shakti Rural Development Society", "NGO")
    decide(admin_token, shakti, "REJECTED", "The FCRA registration number on file could not be matched to an active registration. Resubmit with a current certificate.")

    # A registered CSR account and an individual donor -- both verified, both with a donation
    # history to show in their dashboard.
    register("csr@meridiantech.example", "Ananya Krishnan")
    tcsr = login("csr@meridiantech.example")
    meridian = create_org(tcsr, "Meridian Technologies CSR Foundation", "CSR")
    decide(admin_token, meridian, "APPROVED")
    donate(aadhar, "15000.00", "Ananya Krishnan", "csr@meridiantech.example", "Bengaluru", "Karnataka", token=tcsr, message="Quarterly CSR allocation, elder care.")

    register("ritika.donor@example.com", "Ritika Chandran")
    tdonor = login("ritika.donor@example.com")
    create_org(tdonor, "Ritika Chandran", "INDIVIDUAL")
    donate(sahyoga, "1200.00", "Ritika Chandran", "ritika.donor@example.com", "Pune", "Maharashtra", token=tdonor, project_id=well_project)

    # Anonymous donations -- the no-account path, most of what actually happens on the platform.
    donate(sahyoga, "500.00", "Arjun Mehta", "arjun.mehta@example.com", "Delhi", "Delhi", project_id=well_project)
    donate(udaan, "2000.00", "Family of Nikhil Bhatt", "nikhil.bhatt@example.com", "Mumbai", "Maharashtra", project_id=roof_project, message="In memory of my grandmother, who taught in a school like this one.")
    donate(aadhar, "300.00", "Sunita Rao", "sunita.rao@example.com", "Chennai", "Tamil Nadu")

    print("Seeded. Sign in as reviewer@imparency.org / demo-seed-password at /admin/login to see the queue.")
    print(f"Sahyoga Rural Trust: {API}/orgs/{sahyoga}")


if __name__ == "__main__":
    main()
