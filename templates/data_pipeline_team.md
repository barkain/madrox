# Data Pipeline Team Template

## Overview

Deploy a data engineering team that designs, implements, and monitors production-grade ETL/ELT pipelines for data warehouses, analytics platforms, and real-time data systems.

**Best for**: ETL pipeline development, data lake ingestion, real-time streaming, multi-source data aggregation

**Team Size**: 5 instances (1 supervisor + 4 workers)

**Estimated Duration**: 2-4 hours depending on pipeline complexity

---

## Team Structure

### Data Engineering Lead (Supervisor)
**Role**: `data_scientist` or `backend_developer`
**Enable Madrox**: ✅ Required (must spawn team members)
**MCP Tools**: PostgreSQL, SQLite (database access for pipeline development)

**Responsibilities**:
- Define pipeline architecture and data flow
- Spawn and manage data engineering specialists
- Coordinate sequential pipeline development
- Ensure data quality and consistency
- Validate pipeline performance and reliability
- Deliver production-ready pipeline with monitoring

### Team Members (Workers)

All team members must be spawned with `parent_instance_id` set to the Data Engineering Lead's instance ID.

#### 1. Data Ingestion Specialist
**Role**: `backend_developer`
**Focus**: Source connectors, API clients, data extraction
**Deliverables**:
- Data source connector implementations
- API client code for external data sources
- Batch and streaming ingestion logic
- Error handling and retry mechanisms
- Ingestion monitoring and logging

#### 2. Transformation Engineer
**Role**: `data_scientist` or `backend_developer`
**Focus**: Data cleaning, enrichment, normalization, business logic
**Deliverables**:
- Data transformation logic (SQL, pandas, Spark)
- Data cleaning and deduplication
- Schema normalization and mapping
- Business rule implementations
- Transformation performance optimization

#### 3. Validation Specialist
**Role**: `qa_engineer` or `data_scientist`
**Focus**: Data quality checks, schema validation, integrity constraints
**Deliverables**:
- Data quality validation rules
- Schema validation and enforcement
- Referential integrity checks
- Data profiling and statistics
- Quality gate implementations

#### 4. Monitoring Engineer
**Role**: `devops_engineer`
**Focus**: Observability, alerting, logging, pipeline health
**Deliverables**:
- Monitoring dashboards and alerts
- Pipeline health checks
- Error logging and notification system
- Performance metrics collection
- SLA monitoring and reporting

---

## Workflow Phases

### Phase 1: Pipeline Design (20-30 minutes)

**Supervisor Actions**:
1. Spawn Data Engineering Lead with `enable_madrox=True`
2. Data Engineering Lead spawns 4 specialists with `parent_instance_id`
3. Analyze data sources and target destination
4. Design pipeline architecture (batch vs streaming, transformation logic)
5. Define data quality requirements and SLAs

**Communication Pattern**:
- Use `broadcast_to_children` to share pipeline requirements
- Workers acknowledge using `reply_to_caller` with design proposals

**Design Artifacts**:
- Data flow diagram (source → ingestion → transformation → validation → destination)
- Schema mapping (source schemas → target schema)
- Transformation logic specification
- Data quality rules and constraints
- SLA targets (latency, throughput, data freshness)

**Success Criteria**:
- All 4 specialists spawned and acknowledged
- Pipeline architecture defined and agreed upon
- Data sources and destination identified
- Quality requirements established

### Phase 2: Ingestion Implementation (30-45 minutes)

**Supervisor Actions**:
1. Data Ingestion Specialist implements source connectors
2. Test connectivity to data sources
3. Implement batch or streaming ingestion logic
4. Add error handling and retry mechanisms
5. Data Engineering Lead validates ingestion works

**Communication Pattern**:
- Data Ingestion Specialist uses `reply_to_caller` every 15 minutes with progress
- Data Engineering Lead tests ingestion output via `send_to_instance`

**Ingestion Patterns**:
- **Batch Ingestion**: Scheduled jobs (cron, Airflow), full or incremental loads
- **Streaming Ingestion**: Kafka, Kinesis, Pub/Sub consumers
- **API Ingestion**: REST API polling, webhook receivers
- **File Ingestion**: S3, GCS, SFTP file watchers

**Success Criteria**:
- Data successfully extracted from sources
- Error handling and retries implemented
- Ingestion monitoring and logging added
- Output data passed to Transformation Engineer

### Phase 3: Transformation Implementation (40-60 minutes)

**Supervisor Actions**:
1. Transformation Engineer receives ingestion output
2. Implement data cleaning and normalization
3. Apply business logic transformations
4. Optimize transformation performance
5. Data Engineering Lead validates transformation correctness

**Communication Pattern**:
- Use `send_to_instance` to pass ingestion output to Transformation Engineer
- Transformation Engineer uses `reply_to_caller` with transformation results
- Validation Specialist reviews transformation logic in parallel

**Transformation Types**:
- **Cleaning**: Deduplication, null handling, data type conversions
- **Normalization**: Schema mapping, denormalization for analytics
- **Enrichment**: Joining with reference data, calculated fields
- **Aggregation**: Rollups, summaries, windowing functions
- **Business Logic**: Domain-specific rules and calculations

**Success Criteria**:
- Data cleaned and normalized
- Business logic correctly applied
- Transformation performance acceptable (<5 sec per 10K rows)
- Output data passed to Validation Specialist

### Phase 4: Validation Implementation (20-30 minutes)

**Supervisor Actions**:
1. Validation Specialist receives transformation output
2. Implement data quality checks
3. Enforce schema validation
4. Check referential integrity constraints
5. Generate data quality report

**Communication Pattern**:
- Use `send_to_instance` to pass transformation output to Validation Specialist
- Validation Specialist uses `reply_to_caller` with validation results
- Failed validations trigger alerts to Data Engineering Lead

**Validation Types**:
- **Schema Validation**: Column presence, data types, format constraints
- **Data Quality**: Null checks, range validation, regex patterns
- **Referential Integrity**: Foreign key checks, uniqueness constraints
- **Business Rules**: Domain-specific validation (e.g., date ranges, status transitions)
- **Statistical Profiling**: Min/max/avg/stddev, outlier detection

**Success Criteria**:
- All validation rules implemented
- Quality gates pass (e.g., <1% null values, 100% schema compliance)
- Validation failures logged and reported
- Validated data ready for destination load

### Phase 5: Monitoring Implementation (20-30 minutes)

**Supervisor Actions**:
1. Monitoring Engineer instruments pipeline with observability
2. Implement health checks and alerts
3. Set up logging and error notification
4. Create monitoring dashboard
5. Define SLA monitoring and reporting

**Communication Pattern**:
- Use `broadcast_to_children` to share monitoring requirements with all specialists
- Monitoring Engineer uses `reply_to_caller` with monitoring setup details

**Monitoring Components**:
- **Pipeline Metrics**: Rows processed, processing time, throughput
- **Error Metrics**: Error rate, retry counts, failure reasons
- **Data Quality Metrics**: Validation pass rate, null percentage, schema compliance
- **SLA Metrics**: Data freshness, latency, uptime
- **Alerts**: Threshold alerts (error rate >5%, latency >10 min)

**Success Criteria**:
- Monitoring dashboard created
- Alerts configured and tested
- Logging captured all pipeline stages
- SLA metrics tracked

### Phase 6: Integration Testing & Deployment (20-30 minutes)

**Supervisor Actions**:
1. Data Engineering Lead coordinates end-to-end pipeline test
2. Run pipeline with sample data
3. Validate output in destination system
4. Performance testing (throughput, latency)
5. Deploy pipeline to production

**Communication Pattern**:
- Use `coordinate_instances` with `coordination_type="sequential"` for full pipeline test
- All workers use `reply_to_caller` with test results
- Data Engineering Lead aggregates and validates

**Testing Checklist**:
- ✅ Ingestion successfully extracts data from sources
- ✅ Transformation correctly cleans and transforms data
- ✅ Validation enforces quality gates
- ✅ Data successfully loaded to destination
- ✅ Monitoring captures metrics and logs
- ✅ Alerts trigger on simulated failures
- ✅ Performance meets SLA targets

**Success Criteria**:
- End-to-end pipeline test passes
- Performance meets SLA (e.g., <10 min latency, >10K rows/sec throughput)
- Production deployment successful
- Monitoring confirms pipeline health

---

## Communication Protocols

### Sequential Pipeline Handoffs
**Pattern**: Ingestion → Transformation → Validation → Destination

**Tool**: `coordinate_instances` with `coordination_type="sequential"`

**Handoff Protocol**:
1. Upstream worker completes stage
2. Upstream worker uses `reply_to_caller` with output data location
3. Data Engineering Lead validates output
4. Data Engineering Lead uses `send_to_instance` to trigger downstream worker
5. Downstream worker acknowledges and begins processing

### Quality Gate Failures
**Pattern**: Validation Specialist reports quality gate failure

**Worker Action**:
1. Validation Specialist detects quality issue (e.g., 10% null values, threshold is 1%)
2. Validation Specialist uses `reply_to_caller` with "[QUALITY GATE FAILURE]" prefix
3. Data Engineering Lead investigates root cause
4. Upstream worker (Transformation Engineer) fixes issue
5. Re-run pipeline from failed stage

### Real-Time Monitoring
**Pattern**: Monitoring Engineer polls pipeline health every 5 minutes

**Monitoring Loop**:
1. Monitoring Engineer queries pipeline metrics
2. Check error rates, latency, throughput
3. If SLA violation detected, use `reply_to_caller` with "[SLA VIOLATION]" alert
4. Data Engineering Lead investigates and takes corrective action

---

## Pipeline Patterns

### Batch ETL Pipeline

**Schedule**: Hourly, daily, or weekly

**Flow**:
1. Ingestion: Extract data from sources (API, database, files)
2. Transformation: Clean, normalize, apply business logic
3. Validation: Check data quality
4. Load: Write to data warehouse (PostgreSQL, Snowflake, BigQuery)

**Use Cases**:
- Daily sales data aggregation
- Nightly data warehouse refresh
- Weekly analytics report generation

### Streaming Pipeline

**Trigger**: Real-time event stream (Kafka, Kinesis, Pub/Sub)

**Flow**:
1. Ingestion: Consume events from stream
2. Transformation: Window aggregations, real-time calculations
3. Validation: Real-time quality checks
4. Load: Write to real-time datastore (Redis, Elasticsearch, Kafka)

**Use Cases**:
- Real-time clickstream analytics
- IoT sensor data processing
- Financial transaction monitoring

### Multi-Source Aggregation

**Sources**: Multiple APIs, databases, files

**Flow**:
1. Ingestion: Parallel extraction from multiple sources
2. Transformation: Join and aggregate across sources
3. Validation: Cross-source consistency checks
4. Load: Write to unified data model

**Use Cases**:
- Customer 360 data integration
- Multi-cloud data aggregation
- Enterprise data lake ingestion

---

## Error Handling Strategies

### Source Connection Failures
**Symptoms**: Data Ingestion Specialist cannot connect to source

**Actions**:
1. Implement exponential backoff retry (3 attempts, 1s → 2s → 4s delay)
2. If retries exhausted, log error and alert Monitoring Engineer
3. Monitoring Engineer triggers incident alert
4. Data Engineering Lead investigates source availability

### Data Quality Failures
**Symptoms**: Validation Specialist detects quality gate violations

**Actions**:
1. Validation Specialist logs failed records to quarantine table
2. Use `reply_to_caller` to report quality failure to Data Engineering Lead
3. Data Engineering Lead sends issue to Transformation Engineer via `send_to_instance`
4. Transformation Engineer investigates and fixes transformation logic
5. Re-run pipeline for failed data batch

### Performance Degradation
**Symptoms**: Pipeline latency exceeds SLA (e.g., 20 min instead of 10 min)

**Actions**:
1. Monitoring Engineer detects SLA violation
2. Use `reply_to_caller` with performance metrics
3. Data Engineering Lead identifies bottleneck (slow transformation, large data volume)
4. Transformation Engineer optimizes (add indexes, parallelize, reduce data volume)
5. Re-test performance

### Destination Load Failures
**Symptoms**: Cannot write to destination system

**Actions**:
1. Validation Specialist or Monitoring Engineer detects load failure
2. Implement retry with exponential backoff
3. If persistent failure, write to backup location (S3, GCS)
4. Alert Data Engineering Lead
5. Investigate destination availability and capacity

---

## Data Quality Framework

### Quality Dimensions

| Dimension | Description | Checks |
|-----------|-------------|--------|
| **Completeness** | Required fields present | Null checks, missing value detection |
| **Accuracy** | Data correct and precise | Range validation, format validation |
| **Consistency** | Data agrees across sources | Cross-source reconciliation, referential integrity |
| **Timeliness** | Data fresh and up-to-date | Timestamp checks, latency monitoring |
| **Validity** | Data conforms to rules | Schema validation, business rule checks |
| **Uniqueness** | No duplicate records | Deduplication, primary key checks |

### Quality Rules Examples
- **Null Threshold**: <1% null values in required fields
- **Schema Compliance**: 100% of records match target schema
- **Referential Integrity**: 100% of foreign keys valid
- **Data Freshness**: Data <1 hour old for real-time, <24 hours for batch
- **Outlier Detection**: Values within 3 standard deviations of mean

---

## Pipeline Examples

### Sales Data ETL
**Sources**: Salesforce API, internal PostgreSQL database
**Destination**: Snowflake data warehouse
**Schedule**: Daily at 2 AM
**Transformations**: Join sales records with customer data, calculate metrics
**Validation**: Check for null customer IDs, validate sales amounts >$0
**Expected Volume**: 100K records/day
**Duration**: 2 hours

### Real-Time Clickstream Analytics
**Source**: Kafka topic (website events)
**Destination**: Elasticsearch (for dashboards)
**Trigger**: Real-time (consume continuously)
**Transformations**: Session aggregation, user path analysis
**Validation**: Check for valid session IDs, timestamps in order
**Expected Volume**: 10K events/sec
**Duration**: 3 hours (implementation)

### Multi-Cloud Data Lake Ingestion
**Sources**: AWS S3 files, GCP BigQuery tables, Azure Blob Storage
**Destination**: Unified data lake (Delta Lake)
**Schedule**: Hourly incremental loads
**Transformations**: Schema normalization, partition by date
**Validation**: Schema compliance, no duplicate records
**Expected Volume**: 1M records/hour
**Duration**: 4 hours (implementation)

---

## Resource Constraints

### Per-Worker Limits
- **Max Tokens**: 100,000 tokens per worker
- **Max Cost**: $5.00 per worker ($25 total)
- **Timeout**: 240 minutes (4 hours) per worker
- **Max Data Volume**: 10M records per pipeline run

### Team-Wide Limits
- **Max Instances**: 5 (1 lead + 4 workers)
- **Total Duration**: 4 hours maximum (implementation)
- **Total Cost**: $25 maximum
- **Concurrent Operations**: 4 workers (1 per stage)

### Pipeline Performance Targets
- **Batch Latency**: <1 hour for daily pipelines
- **Streaming Latency**: <5 minutes for real-time
- **Throughput**: >10K records/sec for batch, >1K events/sec for streaming
- **Error Rate**: <0.1% of records
- **Data Quality**: >99% pass validation

---

## Success Metrics

### Implementation Metrics
- ✅ All pipeline stages implemented (ingestion, transformation, validation, monitoring)
- ✅ End-to-end pipeline test passes
- ✅ Performance meets SLA targets
- ✅ Monitoring and alerting configured

### Data Quality Metrics
- ✅ >99% of records pass validation
- ✅ <1% null values in required fields
- ✅ 100% schema compliance
- ✅ No duplicate records

### Operational Metrics
- ✅ Pipeline uptime >99.9%
- ✅ Error rate <0.1%
- ✅ Data freshness meets SLA
- ✅ Alerts trigger correctly on failures

### Timeline Metrics
- ✅ Design: <30 minutes
- ✅ Ingestion: <45 minutes
- ✅ Transformation: <60 minutes
- ✅ Validation: <30 minutes
- ✅ Monitoring: <30 minutes
- ✅ Testing & Deployment: <30 minutes
- ✅ Total: <4 hours

---

## Network Topology

```
Data Engineering Lead (Supervisor)
├── Data Ingestion Specialist (Worker)
├── Transformation Engineer (Worker)
├── Validation Specialist (Worker)
└── Monitoring Engineer (Worker)
```

**Hierarchy**: Single-level supervised network
**Communication**: Bidirectional (supervisor ↔ workers)
**Coordination**: Sequential handoffs (ingestion → transformation → validation)

---

## MCP Tool Requirements

### Required for Data Access
- **PostgreSQL MCP**: For PostgreSQL source/destination access
- **SQLite MCP**: For local SQLite database testing

### Optional Tools
- **AWS MCP**: For S3, Kinesis, DynamoDB access
- **GCP MCP**: For BigQuery, Pub/Sub, GCS access
- **Filesystem MCP**: For local file ingestion

---

## Common Pitfalls

### ❌ No Error Handling in Ingestion
**Result**: Pipeline fails on first source connection error
**Solution**: Implement retry logic with exponential backoff, log all errors

### ❌ Missing Data Quality Validation
**Result**: Bad data flows into destination, corrupting analytics
**Solution**: Validation Specialist implements comprehensive quality checks

### ❌ No Monitoring or Alerts
**Result**: Pipeline failures go unnoticed, data becomes stale
**Solution**: Monitoring Engineer instruments pipeline with metrics and alerts

### ❌ Poor Transformation Performance
**Result**: Pipeline latency exceeds SLA, data not fresh
**Solution**: Transformation Engineer optimizes (add indexes, parallelize, reduce data volume)

### ❌ No Idempotency
**Result**: Re-running pipeline creates duplicate records
**Solution**: Implement upsert logic, check for existing records before insert

---

## Advanced Variations

### Large-Scale Pipeline (Multi-Stage Transformation)
Add **Transformation Engineer 2** for complex multi-stage transformations:

```
Data Engineering Lead (Supervisor)
├── Data Ingestion Specialist (Worker)
├── Transformation Engineer 1 (Worker) [Stage 1: Cleaning]
├── Transformation Engineer 2 (Worker) [Stage 2: Business Logic]
├── Validation Specialist (Worker)
└── Monitoring Engineer (Worker)
```

**Team Size**: 6 instances
**Duration**: 5-6 hours
**Use Case**: Complex transformations with >3 stages

### Real-Time Streaming Team
Add **Stream Processing Engineer** for windowing and aggregation:

```
Data Engineering Lead (Supervisor)
├── Stream Ingestion Specialist (Worker) [Kafka consumer]
├── Stream Processing Engineer (Worker) [Windowing, aggregation]
├── Validation Specialist (Worker) [Real-time checks]
└── Monitoring Engineer (Worker)
```

**Team Size**: 5 instances
**Duration**: 4 hours
**Use Case**: Real-time streaming pipelines (Kafka, Kinesis, Pub/Sub)

---

## Template Version

**Version**: 1.0
**Last Updated**: October 2025
**Tested With**: Madrox v1.0, Claude Sonnet 3.5
