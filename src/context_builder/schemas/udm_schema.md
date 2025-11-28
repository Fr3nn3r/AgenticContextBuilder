[UDM SCHEMA: ALLOWED VARIABLES]
ROOT: claim

1. HEADER (Meta-data)
* `claim.header.line_of_business` (String; e.g. 'Property', 'Liability')
* `claim.header.claim_type` (String; e.g. 'first_party', 'liability')
* `claim.header.loss_at` (Date-Time)
* `claim.header.discovered_at` (Date-Time)
* `claim.header.reported_at` (Date-Time)
* `claim.header.jurisdiction` (String; ISO Country Code)
* `claim.header.attributes.{name}` (Dynamic; Policy-specific header tags)

2. INCIDENT (Loss Facts)
* `claim.incident.primary_cause_code` (String; Main cause of loss)
* `claim.incident.secondary_cause_code` (String; Contributing cause)
* `claim.incident.location_country` (String; ISO Code)
* `claim.incident.location_description` (String; Free text)
* `claim.incident.attributes.{name}` (Dynamic; Risk modifiers e.g. 'is_vacant', 'wind_speed')

3. PARTIES (People/Entities)
* `claim.parties.claimants[].role` (String; e.g. 'insured', 'spouse', 'employee')
* `claim.parties.claimants[].attributes.{name}` (Dynamic)

4. FINANCIALS (Money)
* `claim.financials.currency` (String; ISO 4217)
* `claim.financials.amounts[].type` (String; e.g. 'gross_loss', 'deductible', 'limit')
* `claim.financials.amounts[].amount` (Number)
* `claim.financials.amounts[].attributes.{name}` (Dynamic)
* `claim.financials.attributes.{name}` (Dynamic)