# Reach Developments Station
# System Architecture Rules

This document defines the architectural rules governing the Reach Developments Station platform.

These rules are mandatory and must not be violated by contributors, AI agents, or automated coding tools.

The goal is to preserve architectural integrity, maintain system stability, and prevent uncontrolled design drift.

---

# 1. Platform Architecture

The platform follows a **single-service architecture**.

The system must run as a single deployable backend service.

Technology stack:

Backend: FastAPI  
Frontend: Next.js (static export)  
Database: PostgreSQL  
Deployment: Render

---

# 2. Forbidden Architecture Changes

The following architectural changes are not allowed:

• microservices  
• additional backend services  
• separate frontend hosting  
• multiple databases  

The platform must remain simple and maintainable.

---

# 3. Core Data Hierarchy

The system's core data hierarchy must never be modified without architectural review.

Project structure:

Project  
→ Phase  
→ Building  
→ Floor  
→ Unit  

This structure forms the backbone of the entire platform.

All operational workflows depend on it.

---

# 4. Unit-Centric Financial Model

All commercial and financial calculations originate from **Units**.

Units drive:

• pricing  
• sales transactions  
• payment plans  
• revenue calculations  
• commissions  

Financial engines must not bypass unit-level data.

---

# 5. Module Isolation

System modules must remain logically separated.

Modules include:

Land  
Projects  
Units  
Sales  
Construction  
Finance  
Registry  
Settings

Each module must manage its own domain logic.

Example restrictions:

• Pricing engine cannot modify unit registry structure  
• Construction module cannot modify financial calculations  
• Land module cannot create projects automatically  

---

# 6. Assumptions Governance

All feasibility and pricing assumptions must be visible within the system.

Assumptions must include:

• value  
• source  
• last updated date  
• editor  

Assumptions must be tagged with a status:

Confirmed  
Benchmark  
Estimated  
Pending Verification

The system must never hide assumptions inside formulas.

---

# 7. Pull Request Governance

All development changes must follow the canonical PR structure.

Each Pull Request must include:

1. Problem description  
2. Implementation plan  
3. Testing plan  
4. Architecture validation  
5. Documentation updates  

No change should be merged without these elements.

---

# 8. Module Boundaries

Modules must interact through APIs or services.

Direct cross-module data manipulation is discouraged.

Example:

The pricing engine should request unit data rather than modify unit tables directly.

---

# 9. System Navigation

Top-level system navigation must remain consistent.

Navigation structure:

Land | Projects | Units | Sales | Construction | Finance | Registry | Settings

Changes to navigation must be reviewed as product design decisions.

---

# 10. Documentation Integrity

All major architecture changes must be reflected in:

system_specification.md

before implementation begins.

The specification document is the source of truth for the system design.
