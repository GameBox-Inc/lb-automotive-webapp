# LB Automotive Dashboard - Architecture Diagrams

## 1. Current State (Local Development / MVP)
This represents the currently deployed architecture running via Docker Compose.

```mermaid
graph TD
    %% Internet / External
    subgraph "External Access"
        User[User/Staff Browser]
        Twilio[Twilio Voice/SMS]
    end

    %% Ingress & Networking
    subgraph "Docker Host (Network Bridge)"
        Ngrok[Ngrok Tunnel]
        Traefik[Traefik Reverse Proxy]
    end

    %% Application Services
    subgraph "Application Stack"
        Frontend[React Frontend (Vite)]
        Backend[FastAPI Backend (Python)]
        
        %% Data & Support
        Redis[(Redis Cache)]
        SQLite[(SQLite DB Files)]
        Prometheus[Prometheus Metrics]
    end

    %% Connections
    User -- HTTPS (Ngrok URL) --> Ngrok
    Twilio -- Webhooks --> Ngrok
    
    Ngrok -- HTTP --> Traefik
    
    Traefik -- Route / --> Frontend
    Traefik -- Route /api --> Backend
    Traefik -- Metrics --> Prometheus

    Frontend -- API Calls --> Backend
    
    Backend -- Read/Write --> SQLite
    Backend -- Cache/Queue --> Redis
    Backend -- Auth Validations --> SQLite
```

### Component Details
- **Frontend**: React 18, Vite, TailwindCSS. Hosted in Nginx/Node container.
- **Backend**: FastAPI (Python 3.9+). Handles all business logic, RLS, and Twilio integration.
- **Database**: SQLite (file-based). Mounted via Docker volumes.
- **Networking**: Traefik handles internal routing; Ngrok exposes the local env to the internet for Twilio webhooks and remote access.

---

## 2. Future State (Production / Cloud Native)
This represents the target architecture for a scalable, secure production deployment.

```mermaid
graph TD
    %% External
    subgraph "Public Internet"
        Client[Client App]
        ExtServices[External Services (Twilio, SendGrid)]
    end

    %% Cloud Infrastructure (AWS/Azure)
    subgraph "Cloud VPC"
        LB[Cloud Load Balancer (ALB/ELB)]
        
        subgraph "Kubernetes Cluster (EKS/AKS)"
            Ingress[Ingress Controller (Nginx/Traefik)]
            
            subgraph "Service Mesh (Linkerd/Istio)"
                API[FastAPI Pods (HPA Enabled)]
                Web[Frontend Pods (CDN Origin)]
                Worker[Celery Workers]
            end
        end

        subgraph "Managed Data Services"
            Postgres[(Managed PostgreSQL (RDS))]
            RedisCluster[(Managed Redis (ElastiCache))]
            Vault[Secrets Manager (Vault/AWS Secrets)]
        end
    end

    %% CI/CD Pipeline
    subgraph "DevOps"
        GitHub[GitHub Repo]
        Actions[GitHub Actions / CI]
        Registry[Container Registry (ECR/ACR)]
    end

    %% Flows
    Client --> LB
    LB --> Ingress
    Ingress --> Web
    Ingress --> API
    
    API --> Postgres
    API --> RedisCluster
    API --> Vault
    
    %% Async Tasks
    API -- Task Queue --> RedisCluster
    RedisCluster --> Worker
    Worker --> Postgres
    Worker --> ExtServices

    %% Deployment
    GitHub -- Push --> Actions
    Actions -- Build --> Registry
    Actions -- Deploy --> Kubernetes Cluster
```

### Improvements & Changes
1.  **Database**: Migrate from SQLite to **Managed PostgreSQL** for concurrency, backups, and native RLS support.
2.  **Orchestration**: Move from Docker Compose to **Kubernetes** for auto-scaling and zero-downtime deployments.
3.  **Security**:
    -   Replace `.env` files with a dedicated **Secrets Manager**.
    -   Implement **WAF** at the Load Balancer level.
    -   Strict **Network Policies** within the cluster.
4.  **Async Processing**: Introduce **Celery Workers** for heavy tasks (e.g., generating reports, long-running AI tasks) to keep the API responsive.
5.  **CI/CD**: Automated testing and deployment pipelines.

---

## 3. Unified Availability Architecture
This diagram illustrates how the IVR and Web/Onsite systems share the same calendar logic while offering different user experiences ("Variety" vs. "Simplicity").

```mermaid
graph TD
    %% Data Layer
    subgraph "Data Storage"
        DB[(Database: SQLite/Postgres)]
        Tables[Tables: Appointments, Staff_Schedules, Services]
    end

    %% Logic Layer
    subgraph "Backend Logic (Unified Availability Engine)"
        SlotLogic[get_available_slots()]
        
        %% Logic breakdown
        Tables --> SlotLogic
        SlotLogic -- "1. Fetch Staff Shifts" --> DB
        SlotLogic -- "2. Subtract Existing Appts" --> DB
        SlotLogic -- "3. Generate 15-min Blocks" --> RawSlots[Raw Available Slots]
    end

    %% Presentation Layer
    subgraph "Channels / Consumers"
        
        %% Channel A: Web/Kiosk (High Variety)
        subgraph "Web & Kiosk"
            WebUI[Frontend / Kiosk UI]
            WebUI -- "GET /available-slots" --> SlotLogic
            RawSlots -- "Return ALL 15-min slots" --> WebUI
            WebUI -- "Display Grid (9:00, 9:15, 9:30...)" --> User[Onsite/Web User]
        end

        %% Channel B: IVR (Simplified Selection)
        subgraph "IVR / Voice (Twilio)"
            VoiceLogic[Twilio Webhook]
            VoiceLogic -- "1. Get Slots" --> SlotLogic
            
            %% Aggregation Logic
            RawSlots -- "2. Filter & Aggregate" --> Aggregator{Slot Aggregator}
            Aggregator -- "Has Morning Slot?" --> Option1["Press 1 for Morning (9am)"]
            Aggregator -- "Has Afternoon Slot?" --> Option2["Press 2 for Afternoon (2pm)"]
            
            Option1 & Option2 -- "TTS Readout" --> PhoneUser[Phone Caller]
        end
    end

    %% Booking Flow
    User -- "Book Specific Time" --> DB
    PhoneUser -- "Book General Time" --> VoiceLogic
    VoiceLogic -- "Resolve to Best Available 15-min Slot" --> DB
```

### Key Concepts
1.  **Single Source of Truth**: Both systems query the exact same `Staff_Schedules` vs `Appointments` logic. There is no separate "IVR Calendar."
2.  **Differential Exposure**:
    -   **Web/Kiosk**: Receives the raw, granular 15-minute intervals. The user has visual bandwidth to select from 20+ options.
    -   **IVR**: The backend (or webhook logic) post-processes the raw slots into "buckets" (Morning/Afternoon) to match limited cognitive bandwidth on a voice call.
3.  **Conflict Resolution**: Since the underlying DB is shared, an IVR booking instantly reserves the time, preventing a double booking on the Kiosk, and vice-versa.
