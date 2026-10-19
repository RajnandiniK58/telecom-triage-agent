from app.tools import lookup_customer_profile, lookup_knowledge, lookup_network_status


def test_customer_found_case_insensitive():
    assert lookup_customer_profile("cust1001")["name"] == "Aarav Mehta"


def test_customer_not_found():
    assert lookup_customer_profile("NOPE") == {"error": "Customer not found"}


def test_network_status_case_insensitive():
    assert lookup_network_status(" mumbai ")["outage"] is True


def test_network_city_not_found():
    assert lookup_network_status("Atlantis") == {"error": "City not found"}


def test_every_category_has_a_knowledge_article():
    from app.schemas import Category

    for category in Category:
        assert "error" not in lookup_knowledge(category.value), category
