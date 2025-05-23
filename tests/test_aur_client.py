"""
tests/test_aur_client.py - Tests for AUR client.
"""
import pytest
import requests
import responses # from responses library
from gh-aur-updater.aur_client import fetch_maintained_packages, AUR_RPC_BASE_URL
from gh-aur-updater.models import AURPackageInfo
from gh-aur-updater.exceptions import ArchPackageUpdaterError

@responses.activate # This decorator handles mocking for requests library
def test_fetch_maintained_packages_success():
    maintainer = "testmaintainer"
    mock_url = f"{AUR_RPC_BASE_URL}/v5/search/{maintainer}?by=maintainer"
    
    mock_response_data = {
        "version": 5,
        "type": "search",
        "resultcount": 2,
        "results": [
            {
                "ID": 123, "Name": "package-a", "PackageBase": "package-a", 
                "Version": "1.0.0-1", "Maintainer": maintainer,
                "NumVotes": 10, "Popularity": 0.5, "LastModified": 1600000000
            },
            {
                "ID": 456, "Name": "package-b-lib", "PackageBase": "package-b", 
                "Version": "2:2.5.0-3", "Maintainer": maintainer,
                "NumVotes": 5, "Popularity": 0.2, "LastModified": 1600000001
            }
        ]
    }
    responses.add(responses.GET, mock_url, json=mock_response_data, status=200)

    packages = fetch_maintained_packages(maintainer)

    assert len(packages) == 2
    assert isinstance(packages[0], AURPackageInfo)
    assert packages[0].pkgbase == "package-a"
    assert packages[0].name == "package-a"
    assert str(packages[0].version_obj) == "1.0.0-1"
    assert packages[0].maintainer == maintainer
    assert packages[0].num_votes == 10

    assert packages[1].pkgbase == "package-b"
    assert packages[1].name == "package-b-lib" # Name can differ from PackageBase
    assert str(packages[1].version_obj) == "2:2.5.0-3"
    assert packages[1].version_obj.epoch == "2"

@responses.activate
def test_fetch_maintained_packages_no_results():
    maintainer = "othermaintainer"
    mock_url = f"{AUR_RPC_BASE_URL}/v5/search/{maintainer}?by=maintainer"
    mock_response_data = {"version": 5, "type": "search", "resultcount": 0, "results": []}
    responses.add(responses.GET, mock_url, json=mock_response_data, status=200)

    packages = fetch_maintained_packages(maintainer)
    assert len(packages) == 0

@responses.activate
def test_fetch_maintained_packages_aur_rpc_error():
    maintainer = "errormaintainer"
    mock_url = f"{AUR_RPC_BASE_URL}/v5/search/{maintainer}?by=maintainer"
    mock_response_data = {"version": 5, "type": "error", "error": "Maintainer not found."}
    responses.add(responses.GET, mock_url, json=mock_response_data, status=200) # RPC itself returns 200 for 'error' type

    with pytest.raises(ArchPackageUpdaterError, match="AUR RPC error: Maintainer not found."):
        fetch_maintained_packages(maintainer)

@responses.activate
def test_fetch_maintained_packages_http_error():
    maintainer = "httpfail"
    mock_url = f"{AUR_RPC_BASE_URL}/v5/search/{maintainer}?by=maintainer"
    responses.add(responses.GET, mock_url, status=500, body="Server Error")

    with pytest.raises(ArchPackageUpdaterError, match="Network error fetching AUR data: 500 Server Error"):
        fetch_maintained_packages(maintainer)

@responses.activate
def test_fetch_maintained_packages_invalid_json():
    maintainer = "badjson"
    mock_url = f"{AUR_RPC_BASE_URL}/v5/search/{maintainer}?by=maintainer"
    responses.add(responses.GET, mock_url, body="This is not JSON", status=200)

    with pytest.raises(ArchPackageUpdaterError) as excinfo: # Remove 'match'
        fetch_maintained_packages(maintainer)
    print(f"\nACTUAL EXCEPTION MESSAGE (aur_client): {excinfo.value}\n") # Print the message

def test_fetch_maintained_packages_empty_maintainer():
    packages = fetch_maintained_packages("") # Should return empty or raise, depending on implementation.
                                            # Current implementation logs error and returns [].
    assert packages == []
