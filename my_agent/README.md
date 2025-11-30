# JSF2NG: Automated JSF to Angular Migration System

JSF2NG is a coordinated multi-agent migration system engineered using Google's Agent Development Kit. Instead of attempting a monolithic "convert everything" approach, the system mirrors how a real modernization team would operate: specialized agents, each mastering one stage of the migration, orchestrated through a fault-tolerant pipeline.

## Problem Statement

Many enterprises still run critical internal tools and dashboards built on legacy technologies such as JSF (JavaServer Faces). These systems are stable but outdated, and companies face a major challenge:

- New developers are rarely trained in JSF.
- Fresh talent prefers Angular, React, or modern frameworks.
- Companies must either spend money training developers in JSF or rewrite their legacy UIs entirely — both costly options.

Because of this talent gap, organizations struggle to maintain or modernize these legacy JSF pages. A tool that automatically converts JSF pages into Angular components removes this barrier, reduces migration cost, and gives teams an immediate upgrade path.

## Why Agents?

Agents solve the modernization problem by breaking a complex migration workflow into specialized steps:

- A Scanner Agent to detect patterns in JSF pages.
- A Logic Extractor Agent for EL expressions and JSF actions.
- A Visual Extractor Agent for UI structure.
- An Architect Agent that designs Angular equivalents.
- A Code Generator Agent for writing Angular components.
- An Evaluator Agent for automated quality scoring.
- Infrastructure for memory, sessions, retries, context compaction, and observability.

## Architecture

JSF2NG is a coordinated multi-agent migration system. At the center of the system is the Migration Orchestrator, which manages memory, concurrency, retries, pausing/resuming, and inter-agent communication. Around it, a series of specialized agents form the JSF-to-Angular translation ecosystem.

![Architecture Diagram](https://www.googleapis.com/download/storage/v1/b/kaggle-user-content/o/inbox%2F29816471%2F451b27dd1a431bbc8a105c17d2a2b7bb%2FArchitecture.png?generation=1764266807982787&alt=media)

### 1. Bootstrap Pipeline — The System Analyst Team

Before any migration begins, JSF2NG performs a global pass over the input application.

* **Project_Scanner (Frontend Research Analyst):** Reads all `.xhtml` pages to extract project-level intelligence, including global bean references, data tables, PrimeFaces components, dialogs, and CSS class patterns. This creates a unified picture of the application's JSF design language.
* **Memory_Persistor (Knowledge Archivist):** Stores this project-wide metadata into an ephemeral `MemoryBank` (saved as `project_memory.json`). This memory ensures agents have a shared understanding of the global context.

### 2. Migration Pipeline — The Multi-Agent Conversion Assembly Line

For each JSF page, JSF2NG runs a sequential agent pipeline:

* **JSF_Logic_Extractor (Behavioral Analyst):** Reads the page to extract EL expressions (`#{bean.property}`), action listeners, table bindings, form bindings, and validation rules. It defines the functional contract.
* **JSF_Visual_Extractor (UI Structure Analyst):** Reads the raw text to determine layout structure, components used (`panelGrid`, `dialogs`), hierarchical composition, and inline styles. It creates the visual blueprint.
* **Angular_Architect (Solution Architect):** Uses Google Search to map PrimeFaces components to Angular equivalents (e.g., `p:dataTable` to `mat-table`, `p:commandButton` to `mat-button`). It synthesizes upstream inputs into a detailed migration blueprint defining component names, services, routing, and form structures.
* **Angular_Code_Generator (Code Implementation Engineer):** Converts the blueprint into working Angular files (`component.ts`, `component.html`, `component.css`, `service.ts`). It applies specific rules, such as ensuring dashboards subscribe to services and forms follow Angular best practices.
* **Migration_Evaluator (Quality Inspector):** Checks structure completeness, mapping accuracy, and adherence to best practices, outputting a structured evaluation score (0-10) and report.

### 3. Core Infrastructure

The system relies on a custom runtime engine to handle real-world engineering challenges:

* **MemoryBank:** An ephemeral shared brain that stores inter-agent project data and is auto-deleted after execution.
* **SessionManager:** A pause/resume/cancel engine that allows long-running operations to be controlled, which is critical when dealing with rate-limited APIs.
* **A2A Messenger:** An Agent-to-Agent communication bus allowing agents to exchange structured messages.
* **Observability Suite:**
    * `logs.jsonl`: Tracks every action, duration, tool call, and error.
    * `metrics.json`: Tracks success rates and migration counts.
    * Evaluation reports: Generated for quality scoring.
* **Concurrency + Retry Engine:** Supports bounded concurrency, quota-safe backoff (`QUOTA_BACKOFF_INITIAL`), automatic retries (`MAX_RETRIES`), and transient-failure detection.
* **Context Compaction:** Automatically trims oversized payloads before sending them to the LLM to prevent failures and reduce costs.

## Setup and Installation

### Prerequisites
* Python 3.x
* Google Agent Development Kit (ADK)
* Google Cloud API Key

### Configuration

Create a `.env` file in the project root with the following configurations:

```env
GOOGLE_API_KEY=your_google_api_key
```

Directory Structure
The system expects the following directory structure:
- ```/input```: Place legacy .xhtml files here.
- ```/output```: Generated Angular components will appear here.
- ```/observability```: Logs and metrics will be written here.
- ```/memory```: Temporary storage for the MemoryBank (cleared on run).

## Usage
1. **Place Files**: Drop your JSF ```.xhtml``` files into the ```/input``` directory.

2. **Run the System**:
```bash 
python JSF2NG.py
```
3. **Monitor**: Check the console for progress or tail ```/observability/logs.jsonl```.

4. **Review Output**: Navigate to ```/output/<page_name>``` to view the generated Angular files.

## Output format
For a file named ```Login.xhtml```, the system generates a folder ```/output/Login/``` containing:

- **auth.service.ts**: Handles API communication (using ```HttpClient```, ```catchError```, and ```Observable```).

- **login.component.ts**: The component logic (Imports, Component decorator, properties, and methods).

- **login.component.html**: The template with Angular Material mappings (e.g., ```p-card```, ```p-messages```).

- **login.component.css**: The component-specific styles.

Observability and Evaluation
The system generates detailed reports to ensure transparency:
- Logs: stored in ```/observability/logs.jsonl```.
- Metrics: stored in ```/observability/metrics.json```.
- Evaluation: A JSON file containing scores and summaries for every migrated page.
Example Evaluation snippet:
```JSON
"login.xhtml": {
  "score": 9.0,
  "issues": [],
  "summary": "Logic report... bean_method_calls: ['#{authBean.login}']... validations: ['required=\"true\"']..."
}
```
## Future Improvements
If extended, the following features would be added:

- Full JSF application migration (beans, models, Java backend to Angular + Spring Boot).

- Generation of complete Angular app structure (routing, modules, index.html).

- Pixel-perfect PrimeFaces to Angular Material UI mapping.

- Compile-time validation for generated Angular code.

- SaaS deployment with an upload-based migration UI.

- A visual dashboard showing migration statistics and logs.