# ARD — Система багатоконтурної детекції дезінформації

**Architecture Requirements Document** для асистента аналітика з виявлення маніпуляцій і дезінформації (FIMI / інформаційні операції).



## 1. Purpose

Побудувати **пояснюваний аналітичний пайплайн**, який приймає повідомлення з інформаційного поля (Telegram, X, Facebook, форварди, посилання) і допомагає людині-аналітику відповісти на два **незалежні** питання:


| Вимір                     | Питання                                                                    | Не плутати з      |
| ------------------------- | -------------------------------------------------------------------------- | ----------------- |
| **Маніпуляція (форма)**   | Чи текст риторично маніпулятивний? Які техніки? Де саме в тексті?          | істинністю фактів |
| **Дезінформація (зміст)** | Чи перевірювані твердження хибні / оманливі? На чому ґрунтується висновок? | силою емоцій      |


Система **не замінює** аналітика там, де ціна помилки висока. Вона прискорює triage, структурує докази й явно позначає **abstention**, коли даних недостатньо.

### 1.1 Користувачі та контекст

- **Аналітик / модератор** — отримує структурований звіт з підсвіткою фрагментів, технік, claims і citations.
- **Контекст** — українськомовне та змішане інформаційне поле; джерела FIMI (EUvsDisinfo, власні корпуси); вхід часто «брудний»: форварди, emoji, URL без тексту, YouTube без транскрипту в payload.

### 1.2 Межі системи

**В scope:**

- Ingestion і нормалізація входу (текст, URL → контент).
- Три аналітичні контури + synthesis (verifier).
- Evidence-grounded fact-check з abstention.
- Аудитований вихід для UI / API.
- Eval loop і observability для ітерацій якості.

**Поза scope (v1):**

- Автономна публікація вердиктів без human review.
- Детекція ботів / координованої поведінки (окремий шар).
- Fine-tuning / edge deployment (наступні фази розвитку системи).
- Повноцінний RAG над власним корпусом (можливе розширення retrieval).

### 1.3 Принцип проєктування

> **Autonomy must be earned** — рівень автономності оркестрації (workflow → agent → multi-agent) обирається **після** eval, а не до нього.

Domain logic (контури) реалізується **один раз** і не залежить від того, чи кроки викликає фіксований граф, чи ReAct-агент.

---

## 2. Problem — що саме вирішуємо

### 2.1 Вхід

Мінімальний контракт:

```json
{
  "source": "tg | x | fb | …",
  "post_body": "сирий текст або повідомлення з посиланням",
  "author_id": "ідентифікатор автора в джерелі",
  "metadata": { "url": "…", "timestamp": "…" }
}
```

На практиці `post_body` може бути: чистий текст, форвард з шумом, голе посилання на відео/статтю.

### 2.2 Вихід

Структурована відповідь для фронту / аналітика — два блоки, як у ранній специфікації, але з явним розділенням вимірів:

```json
{
  "is_manipulative": true,
  "manipulation": {
    "techniques": ["fear_appeal", "urgency"],
    "triggers": ["ТЕРМІНОВО!!!", "Забирайте готівку ЗАРАЗ"],
    "explanation": "…"
  },
  "is_disinformation": true,
  "disinformation": {
    "claims_checked": [
      { "claim": "…", "verdict": "refuted", "evidence": [{ "source": "url", "snippet": "…" }] }
    ],
    "explanation": "…"
  },
  "verdict": "likely_disinformation | likely_reliable | mixed | unverified",
  "abstention": false,
  "audit_log": ["…"]
}
```

Текст може бути маніпулятивним без дезінформації і навпаки — UI і метрики **не зливають** ці осі в один score.

### 2.3 Типові failure modes (чому потрібен ARD, а не «просто промпт»)


| Failure                     | Приклад                                   | Наслідок без boundary                        |
| --------------------------- | ----------------------------------------- | -------------------------------------------- |
| **Bad input**               | Скринінг сирого YouTube URL як тексту     | Plausible-but-wrong verdict («fake success») |
| **Missing state**           | Фактчек без попереднього виділення claims | Галюцинація перевірки                        |
| **Stale / wrong knowledge** | Модель «знає» факт з weights              | Хибний refute без citation                   |
| **Over-confidence**         | Емоційний genuine пост                    | False positive на дезінформацію              |
| **Under-confidence**        | Сатира без claims                         | Зайвий fact-check spend                      |


Система має явно обробляти перші три через **ingestion**, **контури** і **retrieval**; останні два — через **screening policy** і **abstention**.

---

## 3. Data — вимоги до даних

> Спочатку дані й критерії успіху, потім архітектура.

### 3.1 Питання про дані (чеклист)


| Питання                         | Вимога для системи                                                                                              |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Source of truth для фактів      | Зовнішні перевірені джерела (web search, офіційні debunk DB, trusted domains) — **не** parametric memory моделі |
| Source of truth для маніпуляцій | Сам текст + розмічені корпуси (UNLP, власна анотація технік)                                                    |
| Static vs dynamic               | Промпти й політики — versioned; факти — dynamic retrieval на кожен claim                                        |
| Safe vs sensitive               | Класифікація входу; мінімізація PII в логах; sandbox для subprocess (yt-dlp тощо)                               |
| Поведінка при нестачі даних     | `unverified` + `abstention: true` — валідний prod-вихід                                                         |


### 3.2 Типи вхідних даних (ingestion surface)


| Тип               | Приклад                        | Обов'язковий pre-step     |
| ----------------- | ------------------------------ | ------------------------- |
| **plain text**    | Пост у Telegram                | нормалізація (опційно)    |
| **forward noise** | `Fwd:` + emoji + zero-width    | strip / normalize         |
| **article URL**   | «Перевір цю статтю: https://…» | fetch (Extract / scraper) |
| **video URL**     | YouTube / Shorts               | transcript (yt-dlp / API) |
| **mixed**         | Текст + посилання              | визначити primary content |


Помилка fetch не має валити пайплайн: повертається `FETCH_FAILED: <reason>`, аналітик і наступні контури бачать це в trace.

### 3.3 Дані для evaluation (не «потім», а design input)

Мінімум для PoC — **10–20 чесно розмічених** прикладів; далі — regression suite і held-out test.


| Набір                  | Призначення                          | Що розмічати                                                                 |
| ---------------------- | ------------------------------------ | ---------------------------------------------------------------------------- |
| **Core**               | Регресія якості контурів             | `is_manipulative`, `gold_verdict`, `has_checkable_claim`, техніки            |
| **Ingestion-hard**     | Входи з URL / шумом                  | `requires_fetch`, `content_resolved` (чи система прочитала реальний контент) |
| **Real debunks**       | Зовнішня валідація retrieval         | EUvsDisinfo cases + `report_url`                                             |
| **Adversarial / edge** | Сатира, genuine-emotional, ambiguous | Очікуваний abstention                                                        |


У reference implementation: `[eval/dataset.jsonl](eval/dataset.jsonl)`, `[eval/hard_dataset.jsonl](eval/hard_dataset.jsonl)`, `[eval/euvsdisinfo_cases.jsonl](eval/euvsdisinfo_cases.jsonl)`.

### 3.4 Внутрішні контракти між кроками (typed state)

Кожен контур повертає **валідовану** структуру (Pydantic / JSON Schema):


| Контур        | Output model              | Ключові поля                                                                |
| ------------- | ------------------------- | --------------------------------------------------------------------------- |
| 1. Screening  | `ScreeningProfile`        | `manipulation_probability`, `techniques`, `triggers` (verbatim), `escalate` |
| 2. Narrative  | `ClaimBundle`             | `narrative`, `actors_and_roles`, `intent`, `claims[]`, `query_hints[]`      |
| 3. Fact-check | `FactVerdict` (per claim) | `verdict`, `evidence[]` з provenance                                        |
| Synthesis     | `FinalDecision`           | окремо forma / content + `abstention`                                       |


Специфікація моделей: `[src/state.py](src/state.py)`.

---

## 4. Evaluation — до вибору архітектури

Evals — **ключ до вибору** workflow vs agent, а не «enterprise maturity extra».

### 4.1 Декомпозиція: метрика на кожен атомарний крок


| Крок             | Метрика                                             | Навіщо                             |
| ---------------- | --------------------------------------------------- | ---------------------------------- |
| Ingestion        | `content_resolved`                                  | Ловить fake success при URL-входах |
| Screening        | `manipulation_correct`, per-technique recall        | Форма окремо від вердикту          |
| Claim extraction | claim coverage, atomicity (manual / LLM-judge)      | Без claims немає fact-check        |
| Retrieval        | retrieval precision@k, source trust                 | Evaluate **окремо** від answer     |
| Fact-check       | per-claim `refuted/supported/unverifiable` accuracy | Evidence-bounded                   |
| Synthesis        | `verdict_exact`, `abstention_correct`               | End-to-end, але не єдина метрика   |
| Operations       | latency, tokens, tool calls, cost                   | Порівняння варіантів оркестрації   |
| Stability        | verdict variance при N runs                         | Debuggability multi-agent          |


**Критично:** високий `verdict_exact` при `content_resolved = 0` — сигнал **поганої системи**, навіть якщо «accuracy» виглядає прийнятно.

### 4.2 Три шари eval (prod-логіка)

```
1. Regression suite     — щоденний/CI прогін на core + real debunks
2. Contrastive suite    — входи, де ламається фіксований path (ingestion, normalization)
3. Operational suite    — variance, trace depth, coordination cost (multi-agent drift)
```

Reference scripts: `[eval/run_eval.py](eval/run_eval.py)`, `[eval/run_contrastive.py](eval/run_contrastive.py)`, `[eval/debuggability.py](eval/debuggability.py)`. Дизайн contrastive: `[docs/specs/2026-06-20-contrastive-evals-design.md](docs/specs/2026-06-20-contrastive-evals-design.md)`.

### 4.3 Build loop (порядок delivery)

1. Define evals, metrics, benchmark.
2. 10–20 labeled samples → перші `input → expected` mappings.
3. Baseline на сильній моделі (frontier) для якості.
4. Ітерації промптів / retrieval / routing; regression після кожної зміни.
5. Оптимізація вартості (менша модель) **лише до** порогу якості на eval.
6. Збір прод-даних → sanitize → annotate → розширення benchmark.
7. (Опційно) fine-tune, коли pattern стабільний.

### 4.4 Observability

Кожен run має trace: state transitions, tool calls, routing, retries. Порядок дебагу: **state → branch → tool → output contract → prompt**.

Prod: Langfuse / Logfire / власний OTel — не принципово для ARD; принципово — **traceability is not optional**.

### 4.5 Eval tooling: pydantic-evals vs custom harness


| Підхід                                                                     | Коли                                                             |
| -------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| **pydantic-evals** (`Case` + `Evaluator` → `Dataset` → `EvaluationReport`) | Eval suite зростає, CI regression, багато custom evaluators      |
| **Custom JSONL + scripts**                                                 | PoC, навчальний контур, кастомні метрики типу `content_resolved` |
| **Langfuse scores**                                                        | Прив'язка eval signal до production traces                       |


Mental model однаковий: evals = unit tests для LLM-пайплайна. Reference implementation залишається на custom harness для прозорості; prod-ітерація 2 логічно мігрує на pydantic-evals.

---

## 5. Architecture — домен і оркестрація

### 5.1 Domain layer (стабільний шар)

Три контури + verifier — спільна бізнес-логіка, незалежна від фреймворку:

```text
вхід (текст / URL)
  → [optional] ingest / normalize
  → контур 1: screen_manipulation      — риторичний ризик, НЕ truth verdict
  → контур 2: analyze_narrative        — наратив, intent, atomic claims
  → контур 3: fact_check_claims        — retrieval + evidence-bounded verdict
  → verifier: synthesize FinalDecision
```

Реалізація: `[src/contours.py](src/contours.py)`. Політики:

- **Early stop** — низький screening risk + немає claims → без дорогого fact-check.
- **Escalation** — високий risk або наявні claims → контур 3.
- **Budget** — max N claims на повідомлення (latency/cost cap).
- **Abstention** — недостатньо evidence → `unverified`, не вигадувати.

### 5.2 Orchestration layer (варіант обирається через eval)

Один і той самий domain layer можна обгорнути по-різному:


| Патерн                          | Коли достатньо                                                   | Ризик                                                  |
| ------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------ |
| **Workflow (fixed graph)**      | Всі кроки відомі заздалегідь; вхід завжди нормалізований текст   | Новий тип входу → silent failure, якщо гілку не додали |
| **Workflow + hardcoded ingest** | Патерн ingestion стабілізувався після discovery                  | Працює, але кожна нова гілка — зміна коду              |
| **Single agent (ReAct)**        | Маршрут залежить від runtime input (URL, fetch, tool choice)     | Non-determinism, вища вартість                         |
| **Multi-agent (supervisor)**    | Потрібна ізоляція контексту / ролей — **якщо eval покращується** | Coordination debt, глибші traces                       |


Діаграми варіантів: `[docs/architectures.md](docs/architectures.md)`.

**Рекомендований шлях для prod:**

1. Почати з **workflow** на нормалізованому тексті (найдешевший passing eval).
2. Contrastive eval на URL/шум → виявити прогалини ingestion.
3. Agent-first **discovery** для нових гілок → **extract & harden** у workflow nodes.
4. Multi-agent — лише якщо виміряне покращення якості або maintainability, не за замовчуванням.

### 5.3 Complexity ladder (який шар додавати)


| Рівень | Capability                 | Умова додавання                                     |
| ------ | -------------------------- | --------------------------------------------------- |
| 1      | Prompt only                | Завжди старт                                        |
| 2      | Prompt + schema            | Потрібен verifiable step output                     |
| 3      | Retrieval                  | Факти зовні; knowledge problem                      |
| 4      | Tools (fetch, search, CLI) | Дія в реальному світі                               |
| 5      | Workflow                   | Кроки стабільні; eval проходить                     |
| 6      | Agent                      | Fixed path невідомий; eval виправдовує              |
| 7      | Fine-tuning                | Стабільний repeated pattern на великому labeled set |


### 5.4 Non-functional requirements


| Категорія           | Вимога                                                                   |
| ------------------- | ------------------------------------------------------------------------ |
| **Latency**         | Bounded fact-check (N claims); паралель screening + narrative де можливо |
| **Cost**            | Screening дешевий; escalation за політикою; token/cost metrics в trace   |
| **Reliability**     | Graceful degradation fetch/search; no crash на одному bad input          |
| **Auditability**    | Кожен claim → evidence; `audit_log`; human-readable explanations (UKR)   |
| **Security**        | No arbitrary shell; pinned binaries; tool permissions                    |
| **Maintainability** | Промпти в файлах; domain decoupled від orchestration                     |
| **Determinism**     | Workflow — детермінований routing; agents — документований drift         |


---

## 6. Stack — орієнтири (не догма)

Вибір стеку — function of control vs speed, **після** eval boundary.


| Компонент     | Варіанти                                        | Нотатка                                                                        |
| ------------- | ----------------------------------------------- | ------------------------------------------------------------------------------ |
| Orchestration | LangGraph, pydantic.ai, vendor SDK, raw API     | LangGraph — явний state graph; pydantic.ai — typed Python prod з evals/logfire |
| LLM           | Frontier для baseline якості → smaller для cost | Один model per step спочатку                                                   |
| Retrieval     | Tavily, власний RAG, trusted-domain search      | Окремий eval на retrieval vs answer                                            |
| Schemas       | pydantic v2                                     | Обов'язково для контурів                                                       |
| Evals         | pydantic-evals, custom, Langfuse scores         | Зростає з maturity                                                             |
| Observability | Langfuse, Logfire, OTel                         | Trace кожного run у prod                                                       |


### Чому pydantic.ai — варіант, а не default у ARD

**pydantic.ai** добре підходить для greenfield Python-сервісу: typed agents, structured output, evals, Logfire в одному стеку.

У цій задачі він **не є єдиним правильним вибором**, бо:

- Domain layer (три контури) має жити **окремо** від agent runtime — інакше важко порівняти workflow vs agent на однаковій capability.
- Потрібні **різні рівні оркестрації** на одному коді контурів — LangGraph (або еквівалентний graph runtime) зручніший для explicit routing і contrastive eval.
- **Ingestion** (yt-dlp, Extract) — tool/skill шар; не вимагає pydantic.ai Agent як цілого.

**Практична порада:** pydantic для schemas + (за потреби) pydantic-evals для CI; pydantic.ai — коли команда фіксується на одному agent framework для prod API, а не для експериментів з autonomy level.

Reference implementation використовує LangGraph + Langfuse, щоб валідувати ці рішення на реальних traces — див. `[README.md](README.md)`.

---

## 7. Acceptance criteria (система)

- [ ] Два виміри (маніпуляція / дезінформація) в API і UI розділені.
- [ ] Abstention — штатний вихід, не помилка.
- [ ] Regression suite на core set: стабільні пороги `manipulation_correct`, `verdict_exact`, `abstention_correct`.
- [ ] Contrastive suite: `content_resolved → 1` на fetch-required входах.
- [ ] Fact-check не виконується без atomic claims з контуру 2.
- [ ] Кожен refuted claim має ≥1 evidence item з source URL.
- [ ] Trace дозволяє відтворити: який контур, який tool, який routing.
- [ ] Workflow baseline проходить eval на plain text; agent/workflow+hardening — на повному ingestion surface.

---

## 8. Ризики та відкриті питання


| Ризик                             | Мітигація                                         |
| --------------------------------- | ------------------------------------------------- |
| Fake success на URL               | `content_resolved` в eval; ingest gate            |
| Retrieval junk                    | Trusted domains, reranker, окремий retrieval eval |
| Multilingual drift (UK/RU/EN)     | Окремі slices в benchmark                         |
| Over-automation                   | Human review на high-impact verdicts              |
| Eval overfitting to 14–20 samples | Held-out test; регулярне поповнення з прод-логів  |


**Відкрито:** per-contour production metrics; власний debunk index vs web-only; політика escalation для сатири; edge deployment.

---

## 9. Reference implementation (demo)

Папка `[demo/](.)` — не окрема «задача», а **зріз системи** для воркшопу й регресії:


| Артефакт                                                           | Що валідує з цього ARD                       |
| ------------------------------------------------------------------ | -------------------------------------------- |
| `contours.py`                                                      | Domain layer (§5.1)                          |
| `workflow_graph.py`, `workflow_with_fetch.py`, `single_agent.py`, `multi_agent.py` | Варіанти оркестрації (§5.2) |
| `eval/`*                                                           | Eval methodology (§4)                        |
| `streamlit_app.py`                                                 | Два виміри + fake-success flag для аналітика |
| `RUNBOOK.md`                                                       | Відтворювані сценарії                        |


Для live-demo на воркшопі: problem → data → eval tables → Langfuse traces → висновок «autonomy must be earned».
