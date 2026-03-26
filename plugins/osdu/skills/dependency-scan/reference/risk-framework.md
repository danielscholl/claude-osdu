# Dependency Update Risk Framework

Use this framework to assess the actual risk of dependency updates, rather than relying solely on semantic versioning.

## Risk Calculation

Sum the modifiers from each factor to get total risk score:
- **LOW** (0-1): Safe to batch, minimal validation
- **MEDIUM** (2-3): Apply individually, standard validation
- **HIGH** (4+): Research first, extended validation, consider deferral

---

## Factor 1: Library Category

| Category | Modifier | Examples |
|----------|----------|----------|
| Framework | +2 | Spring Boot, Spring Framework, Spring Security, Quarkus, Micronaut |
| Data/Serialization | +1 | Jackson, Protobuf, gRPC, Avro |
| Network/HTTP | +1 | Netty, OkHttp, Apache HttpClient, Reactor Netty |
| Database | +1 | JDBC drivers, Hibernate, JPA providers |
| Security | +1 | BouncyCastle, Nimbus JOSE, OAuth libraries |
| Cloud SDK | +1 | Azure SDK, AWS SDK, Google Cloud libraries |
| Utility | 0 | Commons-*, Guava, SLF4J, Lombok |
| Testing | 0 | JUnit, Mockito, AssertJ (dev-only impact) |

---

## Factor 2: Version Jump Magnitude

| Jump Type | Modifier | Detection |
|-----------|----------|-----------|
| Patch | 0 | x.y.Z changes |
| Minor | +1 | x.Y.z changes |
| Major | +3 | X.y.z changes |

---

## Factor 3: CVE Context

| Scenario | Modifier | Reasoning |
|----------|----------|-----------|
| CRITICAL CVE | -1 | Urgency justifies faster action |
| HIGH CVE | 0 | Standard priority |
| MEDIUM/LOW CVE | 0 | Standard priority |
| No CVE (proactive) | +1 | No urgency, be more cautious |

---

## Factor 4: Dependency Depth

| Source | Modifier |
|--------|----------|
| Direct dependency | 0 |
| Transitive (1 level) | 0 |
| Deep transitive (2+) | +1 |

---

## Factor 5: Fix Location

| Location | Modifier |
|----------|----------|
| Proper fix in this service | 0 |
| Temporary override (upstream needed) | +1 |
| Override of BOM-managed dependency | 0 |

---

## Risk Level Actions

### LOW Risk (score 0-1)
- Batch multiple updates in single commit
- Standard mvn verify validation
- No changelog review required

### MEDIUM Risk (score 2-3)
- Individual commits for each update
- Standard mvn verify validation after each
- Brief changelog scan for breaking changes

### HIGH Risk (score 4+)
- Research before applying
- Check migration guides and changelogs
- Extended validation
- Individual commit with detailed message
- Consider deferral if no CVE pressure

---

## Library Category Detection Patterns

| Pattern | Category |
|---------|----------|
| org.springframework.* | Framework |
| io.quarkus.* | Framework |
| com.fasterxml.jackson.* | Serialization |
| com.google.protobuf.* | Serialization |
| io.grpc.* | Serialization |
| io.netty.* | Network |
| org.apache.httpcomponents.* | Network |
| org.postgresql.* | Database |
| com.mysql.* | Database |
| com.azure.* | Cloud SDK |
| software.amazon.awssdk.* | Cloud SDK |
| org.bouncycastle.* | Security |
| com.nimbusds.* | Security |
| org.apache.commons.* | Utility |
| com.google.guava.* | Utility |
| org.slf4j.* | Utility |
| org.junit.* | Testing |
| org.mockito.* | Testing |
