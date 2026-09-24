"""Parametric Cypher queries for Neo4j Knowledge Graph operations."""

# ==============================================================================
# 1. Schema Constraints & Indexes
# ==============================================================================

SCHEMA_CONSTRAINTS = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Airport) REQUIRE a.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (al:Airline) REQUIRE al.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (c:City) REQUIRE c.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (co:Country) REQUIRE co.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (f:Flight) REQUIRE f.flight_number IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (h:Hotel) REQUIRE h.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Policy) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Supplier) REQUIRE s.code IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (b:Booking) REQUIRE b.reference IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (r:Route) REQUIRE r.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (fa:Fare) REQUIRE fa.id IS UNIQUE",
]

# ==============================================================================
# 2. Node Upsert Queries (Idempotent MERGE)
# ==============================================================================

MERGE_COUNTRY = """
MERGE (c:Country {name: $name})
ON CREATE SET c.created_at = datetime()
RETURN c
"""

MERGE_CITY = """
MERGE (ci:City {name: $name})
ON CREATE SET ci.created_at = datetime()
WITH ci
MATCH (co:Country {name: $country_name})
MERGE (ci)-[:LOCATED_IN]->(co)
RETURN ci
"""

MERGE_AIRPORT = """
MERGE (a:Airport {id: $id})
ON CREATE SET a.name = $name,
              a.icao = $icao,
              a.latitude = $latitude,
              a.longitude = $longitude,
              a.timezone = $timezone
ON MATCH SET a.name = $name
WITH a
MATCH (ci:City {name: $city_name})
MERGE (a)-[:LOCATED_IN]->(ci)
RETURN a
"""

MERGE_AIRLINE = """
MERGE (al:Airline {id: $id})
ON CREATE SET al.name = $name,
              al.country = $country,
              al.alliance = $alliance,
              al.logo_url = $logo_url
ON MATCH SET al.alliance = $alliance
RETURN al
"""

MERGE_ROUTE = """
MERGE (r:Route {id: $id})
ON CREATE SET r.origin = $origin, r.destination = $destination, r.distance_km = $distance_km
WITH r
MATCH (orig:Airport {id: $origin})
MATCH (dest:Airport {id: $destination})
MERGE (r)-[:FROM_AIRPORT]->(orig)
MERGE (r)-[:TO_AIRPORT]->(dest)
RETURN r
"""

MERGE_FLIGHT = """
MERGE (f:Flight {flight_number: $flight_number})
ON CREATE SET f.departure_time = $departure_time,
              f.arrival_time = $arrival_time,
              f.duration_minutes = $duration_minutes,
              f.stops = $stops,
              f.aircraft_type = $aircraft_type,
              f.status = $status
WITH f
MATCH (al:Airline {id: $airline_code})
MATCH (orig:Airport {id: $origin_code})
MATCH (dest:Airport {id: $destination_code})
MERGE (al)-[:OPERATES]->(f)
MERGE (f)-[:DEPARTS_FROM]->(orig)
MERGE (f)-[:ARRIVES_AT]->(dest)
RETURN f
"""

MERGE_HOTEL = """
MERGE (h:Hotel {id: $id})
ON CREATE SET h.name = $name,
              h.address = $address,
              h.star_rating = $star_rating
WITH h
MATCH (ci:City {name: $city_name})
MERGE (h)-[:LOCATED_IN]->(ci)
RETURN h
"""

MERGE_SUPPLIER = """
MERGE (s:Supplier {code: $code})
ON CREATE SET s.name = $name, s.supplier_type = $supplier_type
RETURN s
"""

MERGE_SUPPLIER_FLIGHT = """
MATCH (s:Supplier {code: $supplier_code})
MATCH (f:Flight {flight_number: $flight_number})
MERGE (s)-[:PROVIDES]->(f)
"""

MERGE_POLICY = """
MERGE (p:Policy {id: $id})
ON CREATE SET p.entity_type = $entity_type,
              p.entity_id = $entity_id,
              p.policy_type = $policy_type,
              p.title = $title,
              p.content = $content,
              p.version = $version
WITH p
OPTIONAL MATCH (al:Airline {id: $entity_id})
WHERE p.entity_type = 'AIRLINE' AND al IS NOT NULL
FOREACH (_ IN CASE WHEN al IS NOT NULL THEN [1] ELSE [] END |
    MERGE (al)-[:HAS_POLICY]->(p)
)
RETURN p
"""

MERGE_DOCUMENT = """
MERGE (d:Document {id: $id})
ON CREATE SET d.title = $title,
              d.source = $source,
              d.version = $version,
              d.document_type = $document_type
WITH d
OPTIONAL MATCH (p:Policy {id: $policy_id})
FOREACH (_ IN CASE WHEN p IS NOT NULL THEN [1] ELSE [] END |
    MERGE (d)-[:DESCRIBES]->(p)
)
RETURN d
"""

MERGE_FARE = """
MERGE (fa:Fare {id: $id})
ON CREATE SET fa.fare_basis = $fare_basis,
              fa.cabin_class = $cabin_class,
              fa.refundable = $refundable,
              fa.change_fee = $change_fee,
              fa.cancellation_fee = $cancellation_fee
WITH fa
OPTIONAL MATCH (f:Flight {flight_number: $flight_number})
FOREACH (_ IN CASE WHEN f IS NOT NULL THEN [1] ELSE [] END |
    MERGE (f)-[:HAS_FARE]->(fa)
)
RETURN fa
"""

MERGE_BOOKING = """
MERGE (b:Booking {reference: $reference})
ON CREATE SET b.status = $status,
              b.total_amount = $total_amount,
              b.currency = $currency
WITH b
OPTIONAL MATCH (f:Flight {flight_number: $flight_number})
FOREACH (_ IN CASE WHEN f IS NOT NULL THEN [1] ELSE [] END |
    MERGE (b)-[:FOR_FLIGHT]->(f)
)
RETURN b
"""

# ==============================================================================
# 3. Domain Traversal & GraphRAG Retrieval Queries
# ==============================================================================

GET_FLIGHT_FULL_CONTEXT = """
MATCH (al:Airline)-[:OPERATES]->(f:Flight {flight_number: $flight_number})
MATCH (f)-[:DEPARTS_FROM]->(orig:Airport)-[:LOCATED_IN]->(ci_orig:City)
MATCH (f)-[:ARRIVES_AT]->(dest:Airport)-[:LOCATED_IN]->(ci_dest:City)-[:LOCATED_IN]->(co_dest:Country)
OPTIONAL MATCH (al)-[:HAS_POLICY]->(p:Policy)
OPTIONAL MATCH (d:Document)-[:DESCRIBES]->(p)
OPTIONAL MATCH (f)-[:HAS_FARE]->(fa:Fare)
RETURN f, al, orig, ci_orig, dest, ci_dest, co_dest,
       collect(DISTINCT p) AS policies,
       collect(DISTINCT d) AS documents,
       collect(DISTINCT fa) AS fares
"""

GET_AIRLINE_POLICIES = """
MATCH (al:Airline {id: $airline_code})-[:HAS_POLICY]->(p:Policy)
OPTIONAL MATCH (d:Document)-[:DESCRIBES]->(p)
RETURN p, al, collect(DISTINCT d) AS documents
"""

GET_DESTINATION_HOTELS = """
MATCH (a:Airport {id: $airport_code})-[:LOCATED_IN]->(ci:City)<-[:LOCATED_IN]-(h:Hotel)
RETURN h, ci
LIMIT $limit
"""

GET_BOOKING_CONTEXT = """
MATCH (b:Booking {reference: $reference})
OPTIONAL MATCH (b)-[:FOR_FLIGHT]->(f:Flight)
OPTIONAL MATCH (al:Airline)-[:OPERATES]->(f)
OPTIONAL MATCH (f)-[:DEPARTS_FROM]->(orig:Airport)
OPTIONAL MATCH (f)-[:ARRIVES_AT]->(dest:Airport)
OPTIONAL MATCH (al)-[:HAS_POLICY]->(p:Policy)
OPTIONAL MATCH (d:Document)-[:DESCRIBES]->(p)
RETURN b, f, al, orig, dest,
       collect(DISTINCT p) AS policies,
       collect(DISTINCT d) AS documents
"""
