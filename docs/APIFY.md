# Apify TecDoc Car Parts API - Developer Integration Guide

## Overview

This guide explains how to integrate the **TecDoc Car Parts Catalog API** from Apify into your applications. This API provides access to automotive parts data including part identification, cross-referencing, and vehicle compatibility information.

**Actor ID:** `making-data-meaningful/tecdoc`  
**Pricing:** $1.00 per 1,000 results  
**Documentation:** https://apify.com/making-data-meaningful/tecdoc

---

## Prerequisites

1. **Apify Account** with API token (provided by Fred)
2. **Python 3.10+** (recommended) or any language that can make HTTP requests
3. Install the Apify Python client:

```bash
pip install apify-client
```

---

## Authentication

Your API token is found at: https://console.apify.com/settings/integrations

```python
from apify_client import ApifyClient

# Initialize the client with your API token
APIFY_TOKEN = "your-api-token-here"  # Fred will provide this
client = ApifyClient(APIFY_TOKEN)
```

---

## Quick Start Example

Here's a minimal example to search for a part by part number:

```python
from apify_client import ApifyClient

APIFY_TOKEN = "your-api-token-here"
client = ApifyClient(APIFY_TOKEN)

# Define the input for the Actor
run_input = {
    "endpoint": "/searchArticlesByNumber",
    "articleSearchNr": "8W0616887",  # The part number to search
    "langId": 4  # English (see language codes below)
}

# Run the Actor and wait for it to finish
actor_client = client.actor("making-data-meaningful/tecdoc")
run = actor_client.call(run_input=run_input)

# Fetch results from the dataset
dataset_client = client.dataset(run["defaultDatasetId"])
items = dataset_client.list_items().items

print(items)
```

---

## API Endpoints Reference

The Actor supports multiple endpoints. You specify which one to use via the `endpoint` parameter.

### 1. Setup Endpoints (Run Once to Get IDs)

| Endpoint | Purpose | Required Parameters |
|----------|---------|---------------------|
| `/getAllLanguages` | Get all available language IDs | None |
| `/getAllCountries` | Get all country IDs for filtering | None |
| `/listVehicleTypes` | Get vehicle type IDs (car, truck, motorcycle) | None |

### 2. Vehicle Identification Endpoints

| Endpoint | Purpose | Required Parameters |
|----------|---------|---------------------|
| `/getManufacturers` | List car brands | `typeId`, `langId`, `countryFilterId` |
| `/getModels` | List models for a brand | `typeId`, `langId`, `countryFilterId`, `manufacturerId` |
| `/getVehicleEngineTypes` | Get engine variants | `typeId`, `langId`, `countryFilterId`, `manufacturerId`, `modelSeriesId` |
| `/getVehicleDetails` | Full vehicle specs | `typeId`, `langId`, `countryFilterId`, `manufacturerId`, `vehicleId` |

### 3. Parts Search Endpoints

| Endpoint | Purpose | Required Parameters |
|----------|---------|---------------------|
| `/searchArticlesByNumber` | **Search by part number** | `articleSearchNr`, `langId` |
| `/searchArticlesByNumberAndSupplier` | Search with supplier filter | `articleSearchNr`, `supplierId`, `langId` |
| `/getArticlesList` | List parts for a vehicle/category | `typeId`, `langId`, `countryFilterId`, `manufacturerId`, `vehicleId`, `productGroupId` |
| `/getArticleDetailsById` | Full part details | `langId`, `countryFilterId`, `articleId` |

### 4. Category Endpoints

| Endpoint | Purpose | Required Parameters |
|----------|---------|---------------------|
| `/getCategoryV1` | Get part categories (level 1) | `typeId`, `langId`, `countryFilterId`, `manufacturerId`, `vehicleId` |
| `/getCategoryV2` | Get subcategories (level 2) | Same as V1 + `levelId_1` |
| `/getCategoryV3` | Get subcategories (level 3) | Same as V2 + `levelId_2` |

---

## Common Parameter Values

### Language IDs (`langId`)

| ID | Language |
|----|----------|
| 4 | English |
| 1 | German |
| 3 | French |
| 5 | Italian |
| 2 | Spanish |

### Country IDs (`countryFilterId`)

| ID | Country |
|----|---------|
| 62 | Germany |
| 14 | Switzerland |
| 1 | Austria |
| 64 | France |
| 75 | Italy |

### Vehicle Type IDs (`typeId`)

| ID | Type |
|----|------|
| 1 | Automobiles (Passenger Cars) |
| 2 | Commercial Vehicles (Trucks) |
| 3 | Motorcycles |

---

## Complete Integration Example

Here's a full example showing how to search for a part and get detailed information:

```python
from apify_client import ApifyClient
import json

class TecDocClient:
    """Wrapper for the Apify TecDoc API"""
    
    def __init__(self, api_token: str):
        self.client = ApifyClient(api_token)
        self.actor_id = "making-data-meaningful/tecdoc"
        
        # Default settings for Switzerland/German market
        self.default_lang_id = 4  # English
        self.default_country_id = 14  # Switzerland
        self.default_type_id = 1  # Passenger cars
    
    def _run_actor(self, run_input: dict) -> list:
        """Execute the Actor and return results"""
        actor_client = self.client.actor(self.actor_id)
        run = actor_client.call(run_input=run_input)
        
        if run is None:
            raise Exception("Actor run failed")
        
        dataset_client = self.client.dataset(run["defaultDatasetId"])
        return dataset_client.list_items().items
    
    def search_by_part_number(self, part_number: str) -> list:
        """
        Search for a part by its part number (OEM or aftermarket)
        
        Args:
            part_number: The part number to search (e.g., "8W0616887")
        
        Returns:
            List of matching parts with details
        """
        run_input = {
            "endpoint": "/searchArticlesByNumber",
            "articleSearchNr": part_number,
            "langId": self.default_lang_id
        }
        return self._run_actor(run_input)
    
    def get_article_details(self, article_id: str) -> list:
        """
        Get detailed information about a specific article/part
        
        Args:
            article_id: The article ID from a previous search
        
        Returns:
            Detailed part information
        """
        run_input = {
            "endpoint": "/getArticleDetailsById",
            "articleId": article_id,
            "langId": self.default_lang_id,
            "countryFilterId": self.default_country_id
        }
        return self._run_actor(run_input)
    
    def get_manufacturers(self) -> list:
        """Get list of all car manufacturers"""
        run_input = {
            "endpoint": "/getManufacturers",
            "typeId": self.default_type_id,
            "langId": self.default_lang_id,
            "countryFilterId": self.default_country_id
        }
        return self._run_actor(run_input)
    
    def get_models(self, manufacturer_id: int) -> list:
        """Get all models for a manufacturer"""
        run_input = {
            "endpoint": "/getModels",
            "typeId": self.default_type_id,
            "langId": self.default_lang_id,
            "countryFilterId": self.default_country_id,
            "manufacturerId": manufacturer_id
        }
        return self._run_actor(run_input)
    
    def get_vehicle_details(self, manufacturer_id: int, vehicle_id: int) -> list:
        """Get detailed vehicle specifications"""
        run_input = {
            "endpoint": "/getVehicleDetails",
            "typeId": self.default_type_id,
            "langId": self.default_lang_id,
            "countryFilterId": self.default_country_id,
            "manufacturerId": manufacturer_id,
            "vehicleId": vehicle_id
        }
        return self._run_actor(run_input)


# Usage Example
if __name__ == "__main__":
    # Initialize with your API token
    APIFY_TOKEN = "your-api-token-here"
    tecdoc = TecDocClient(APIFY_TOKEN)
    
    # Example 1: Search for a part by number
    print("Searching for part 8W0616887...")
    results = tecdoc.search_by_part_number("8W0616887")
    print(json.dumps(results, indent=2))
    
    # Example 2: Get all manufacturers
    # manufacturers = tecdoc.get_manufacturers()
    # print(json.dumps(manufacturers, indent=2))
```

---

## Async Version (Recommended for Production)

For better performance in production, use the async client:

```python
import asyncio
from apify_client import ApifyClientAsync

async def search_part_async(api_token: str, part_number: str):
    client = ApifyClientAsync(api_token)
    
    run_input = {
        "endpoint": "/searchArticlesByNumber",
        "articleSearchNr": part_number,
        "langId": 4
    }
    
    actor_client = client.actor("making-data-meaningful/tecdoc")
    run = await actor_client.call(run_input=run_input)
    
    dataset_client = client.dataset(run["defaultDatasetId"])
    items = await dataset_client.list_items()
    
    return items.items

# Run it
if __name__ == "__main__":
    results = asyncio.run(search_part_async("your-token", "8W0616887"))
    print(results)
```

---

## HTTP API Alternative (No SDK Required)

If you prefer raw HTTP requests:

```bash
# Start the Actor run
curl -X POST "https://api.apify.com/v2/acts/making-data-meaningful~tecdoc/runs?token=YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "endpoint": "/searchArticlesByNumber",
    "articleSearchNr": "8W0616887",
    "langId": 4
  }'
```

Or use the synchronous endpoint that returns results directly (for runs under 5 minutes):

```bash
curl -X POST "https://api.apify.com/v2/acts/making-data-meaningful~tecdoc/run-sync-get-dataset-items?token=YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "endpoint": "/searchArticlesByNumber",
    "articleSearchNr": "8W0616887",
    "langId": 4
  }'
```

---

## Error Handling

```python
from apify_client import ApifyClient

def safe_search(api_token: str, part_number: str) -> dict:
    """Search with proper error handling"""
    try:
        client = ApifyClient(api_token)
        actor_client = client.actor("making-data-meaningful/tecdoc")
        
        run_input = {
            "endpoint": "/searchArticlesByNumber",
            "articleSearchNr": part_number,
            "langId": 4
        }
        
        run = actor_client.call(run_input=run_input, timeout_secs=120)
        
        if run is None:
            return {"success": False, "error": "Actor run failed", "data": None}
        
        if run.get("status") != "SUCCEEDED":
            return {"success": False, "error": f"Run status: {run.get('status')}", "data": None}
        
        dataset_client = client.dataset(run["defaultDatasetId"])
        items = dataset_client.list_items().items
        
        return {"success": True, "error": None, "data": items}
        
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}
```

---

## Integration with n8n

If integrating with n8n workflows, use the HTTP Request node:

1. **Method:** POST
2. **URL:** `https://api.apify.com/v2/acts/making-data-meaningful~tecdoc/run-sync-get-dataset-items`
3. **Authentication:** Query parameter `token=YOUR_API_TOKEN`
4. **Body (JSON):**
```json
{
  "endpoint": "/searchArticlesByNumber",
  "articleSearchNr": "{{ $json.partNumber }}",
  "langId": 4
}
```

---

## Cost Estimation

- **Pricing:** $1.00 per 1,000 results
- A typical part number search returns 1-50 results
- Estimated cost per lookup: $0.001 - $0.05

---

## Support & Resources

- **Apify Documentation:** https://docs.apify.com/api/client/python
- **Actor Page:** https://apify.com/making-data-meaningful/tecdoc
- **Demo Site:** http://auto-parts-catalog.makingdatameaningful.com/
- **GitHub Example:** https://github.com/ronhartman/tecdoc-autoparts-catalog

---

## Typical Workflow for Insurance Claims

For TrueAim's use case (validating parts in insurance claims):

```python
def validate_claim_part(api_token: str, part_number: str) -> dict:
    """
    Validate a part number from an insurance claim
    
    Returns:
        {
            "valid": bool,
            "part_name": str,
            "manufacturer": str,
            "compatible_vehicles": list,
            "price_range": dict
        }
    """
    tecdoc = TecDocClient(api_token)
    
    results = tecdoc.search_by_part_number(part_number)
    
    if not results:
        return {"valid": False, "part_name": None, "error": "Part not found"}
    
    # Extract relevant information
    part_info = results[0]  # Take first match
    
    return {
        "valid": True,
        "part_number": part_number,
        "part_name": part_info.get("description", "Unknown"),
        "manufacturer": part_info.get("brandName", "Unknown"),
        "article_id": part_info.get("articleId"),
        "raw_data": part_info
    }
```

---

## Questions?

Contact Fred or raise an issue in your internal ticketing system.