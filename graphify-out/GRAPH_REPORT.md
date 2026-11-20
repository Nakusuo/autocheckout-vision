# Graph Report - autocheckout-vision  (2026-11-16)

## Corpus Check
- 140 files · ~76,859 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 7 file(s) not represented in the graph (top: (none) 4, .example 1, .csv 1)

## Summary
- 1504 nodes · 3619 edges · 88 communities (75 shown, 13 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 479 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Máquina de estados Checkout
- CLI del reconocedor
- Filtro de mano y piel
- Pruebas del checkout
- Detector YOLO y vision.py
- Arranque y balanza simulada
- KioskService (núcleo)
- Pruebas del servicio
- API FastAPI del quiosco
- Embedder DINOv2
- Catálogo de productos
- Planes M0-M3 y decisiones
- Fondo y color (reconocedor)
- Pruebas de la API
- Componentes UI y formato
- Verificación JWT y pagos
- Algoritmos de búsqueda (BFS/DFS/A*)
- Registros JSONL
- Desconocidos en cámara
- Config TypeScript app
- Hoja de ruta y milestones
- Utilidades ML y frames
- Problema PesoBandeja
- Benchmark de latencia
- Pasarela de pago y seguridad
- Problema FlujoCompra
- Mock gateway app
- Panel de caja
- Flujo W1-W4 y fusión de peso
- POS simulado y ventas
- package.json UI
- Config Stryker
- TAREAS Criterio 2 - Búsqueda
- Verificador de dataset
- TAREAS Criterio 4 - SVM/KNN/DT/Boosting
- Pruebas de la UI
- Config TypeScript node
- Claves de desarrollo (devkeys)
- Arquitectura de cuatro componentes
- Informe de cambios de cámara
- Hill Climbing
- Lectura de sensores en hilo
- Interfaces de búsqueda (DFS/Problem)
- Integración modo cámara
- Importar fotos del Drive
- Label Studio y catálogo ML
- Pruebas del mock gateway
- Cargos de la pasarela
- Dependencias de desarrollo UI
- Entrenamiento YOLO
- Sistema de diseño AutoCaja
- Pruebas e2e Playwright
- Registro de sesiones
- Dobles de prueba (fakes)
- Cliente API de la UI
- App y Kiosk (UI)
- Pruebas de paneles
- TAREAS Criterio 1 - Cloud y DevOps
- POS y paquete kiosk
- Decisiones de producto (ayuda, sin balanza)
- README y reconocimiento por galería
- Documento informativo
- Filtro de estabilidad
- TAREAS Criterio 5 - Sustentación
- TAREAS Criterio 3 - Regresión y clasificación
- Errores y recalibración
- Botón de ayuda UI
- Guía del equipo y plan APF3
- Reglas clave y pantallas
- Calidad y mutación
- Entrenamiento y benchmark ML
- CLI comparativa de búsqueda
- Interfaz de cámara
- Scripts npm
- Config oxlint
- Dependencias UI
- tsconfig raíz
- Nodo suelto 78
- Nodo suelto 79
- Nodo suelto 80
- Nodo suelto 81
- Nodo suelto 82
- Nodo suelto 85
- Nodo suelto 86
- Nodo suelto 87

## God Nodes (most connected - your core abstractions)
1. `KioskService` - 68 edges
2. `create_app()` - 44 edges
3. `tray()` - 44 edges
4. `TransitionError` - 35 edges
5. `SimulatedScale` - 35 edges
6. `make()` - 34 edges
7. `ticks()` - 33 edges
8. `JwtVerifier` - 32 edges
9. `Catalog` - 31 edges
10. `Checkout` - 30 edges

## Surprising Connections (you probably didn't know these)
- `Riesgos conocidos` --semantically_similar_to--> `Riesgo aceptado: sin balanza`  [INFERRED] [semantically similar]
  docs/DOCUMENTO_INFORMATIVO.md → README.md
- `Alertas de seguridad` --semantically_similar_to--> `Reglas clave del backend`  [INFERRED] [semantically similar]
  README.md → docs/ESTADO.md
- `Ignorar TypeScript mayor (Stryker 10)` --semantically_similar_to--> `TypeScript se queda en 6`  [INFERRED] [semantically similar]
  .github/dependabot.yml → docs/ESTADO.md
- `Contrato de dirección (señalética vial)` --semantically_similar_to--> `La placa de carretera (Creative North Star)`  [INFERRED] [semantically similar]
  .impeccable/surfaces/kiosk-ui-src-kiosk-kiosk-tsx.md → DESIGN.md
- `Quiosco de autocobro AutoCaja` --semantically_similar_to--> `Metas del SRS (ON-01..03, RNF-01..06)`  [INFERRED] [semantically similar]
  PRODUCT.md → docs/DOCUMENTO_INFORMATIVO.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Jobs de CI por componente del monorepo** — github_workflows_ci_job_kiosk_api, github_workflows_ci_job_kiosk_ui, github_workflows_ci_job_mock_gateway, github_workflows_ci_job_ml [EXTRACTED 1.00]
- **Identidad visual AutoCaja (placa, paleta, tipografía)** — design_la_placa_de_carretera, design_paleta_rojo_amarillo_blanco, design_tipografia_overpass, design_unidades_cqw [EXTRACTED 1.00]
- **Cuatro componentes del monorepo** — docs_documento_informativo_kiosk_api, docs_documento_informativo_kiosk_ui, docs_documento_informativo_mock_gateway, docs_documento_informativo_ml [EXTRACTED 1.00]
- **Algoritmos de búsqueda del criterio 2** — docs_plan_apf3_bfs, docs_plan_apf3_dfs, docs_plan_apf3_a_star, docs_plan_apf3_hill_climbing [EXTRACTED 1.00]
- **Modelos comparados en el criterio 4** — docs_plan_apf3_knn, docs_plan_apf3_svm, docs_plan_apf3_arbol_decision, docs_plan_apf3_boosting, docs_plan_apf3_random_forest [EXTRACTED 1.00]
- **Entregables de Cloud y DevOps (criterio 1)** — docs_guia_equipo_tarea_dockerfiles_compose, docs_guia_equipo_tarea_workflow_cd, docs_guia_equipo_tarea_cloud_devops_md [EXTRACTED 1.00]
- **Hitos M0 a M5 del MVP** — docs_superpowers_plans_2026_10_03_hoja_de_ruta_m0, docs_superpowers_plans_2026_10_03_hoja_de_ruta_m2, docs_superpowers_plans_2026_10_03_hoja_de_ruta_m3, docs_superpowers_plans_2026_10_03_hoja_de_ruta_m4, docs_superpowers_plans_2026_10_03_hoja_de_ruta_m5 [EXTRACTED 1.00]
- **Núcleo lógico de kiosk-api (M0)** — kiosk_api_src_kiosk_catalog, kiosk_api_src_kiosk_fusion, kiosk_api_src_kiosk_stability, kiosk_api_src_kiosk_checkout, kiosk_api_src_kiosk_scale [EXTRACTED 1.00]
- **Paquete mltools (herramientas de datos y entrenamiento)** — ml_src_mltools_dataset, ml_src_mltools_frames, ml_src_mltools_labelstudio, ml_src_mltools_bench, ml_src_mltools_split, ml_src_mltools_train [EXTRACTED 1.00]

## Communities (88 total, 13 thin omitted)

### Community 0 - "Máquina de estados Checkout"
Cohesion: 0.09
Nodes (31): Checkout, check_weight(), WeightCheck, Clock, make(), scan(), test_cancel_and_reset_clear_cart_and_weight(), test_cancel_clears_everything_and_records_it() (+23 more)

### Community 1 - "CLI del reconocedor"
Cohesion: 0.09
Nodes (19): benchmark(), build_gallery(), capture(), draw_zone(), Gallery, imread(), leave_one_out(), main() (+11 more)

### Community 2 - "Filtro de mano y piel"
Cohesion: 0.12
Nodes (36): isolate(), remove_hands(), skin_mask(), test_recalibrate_while_detecting_in_another_thread_never_fails(), detector(), fake_embed(), gallery_of(), product_mask() (+28 more)

### Community 3 - "Pruebas del checkout"
Cohesion: 0.11
Nodes (32): scanning(), test_confirm_requires_one_to_three_valid_items(), test_correct_returns_to_scanning(), test_fault_from_any_state_and_recover_to_idle(), test_happy_path_w1_to_w4_and_back(), test_invalid_transition_raises(), test_pay_blocked_when_weight_mismatch(), test_payment_timeout_returns_to_confirming() (+24 more)

### Community 4 - "Detector YOLO y vision.py"
Cohesion: 0.08
Nodes (19): Interfaces cambiables (Detector, ScaleReader, PaymentGateway), class_names_from_metadata(), decode_yolov8(), Detection, FrameSource, ImageFolderSource, letterbox(), YoloOnnxDetector (+11 more)

### Community 5 - "Arranque y balanza simulada"
Cohesion: 0.09
Nodes (19): build_detector(), main(), SimulatedScale, SimulatedTray, test_main_camera_mode_with_simulated_scale_warns_and_has_no_sim_routes(), test_main_camera_that_does_not_open_exits_cleanly(), test_main_starts_sim_kiosk_on_localhost(), test_main_without_api_key_exits() (+11 more)

### Community 6 - "KioskService (núcleo)"
Cohesion: 0.11
Nodes (4): KioskService, test_cancel_records_the_screen_and_report_groups_them(), test_paid_camera_purchase_reopens_camera_when_returning_to_start(), test_sensor_failure_goes_out_of_service_and_recovers()

### Community 7 - "Pruebas del servicio"
Cohesion: 0.13
Nodes (37): make(), paying(), test_a_product_that_stays_in_view_counts_once(), test_auto_reset_happens_exactly_at_ten_seconds(), test_brief_weight_gap_while_placing_raises_no_alarm(), test_cancel_from_scanning_confirming_or_paying_goes_home(), test_cancel_not_allowed_on_w1_or_after_paying(), test_correcting_reopens_the_camera_without_rescanning_the_same_product() (+29 more)

### Community 8 - "API FastAPI del quiosco"
Cohesion: 0.08
Nodes (18): create_app(), act(), cancel(), confirm(), correct(), lifespan(), pay(), recalibrate() (+10 more)

### Community 9 - "Embedder DINOv2"
Cohesion: 0.08
Nodes (19): Embedder, _Camera, fake_models(), _FakeEmbed, FakeSession, photos(), repo(), test_build_detector_camera_with_gallery_uses_similarity() (+11 more)

### Community 10 - "Catálogo de productos"
Cohesion: 0.15
Nodes (13): Catalog, Product, init_db(), load_catalog(), catalogo(), test_from_csv_loads_products(), test_get_unknown_sku_returns_none(), test_invalid_products_are_rejected() (+5 more)

### Community 11 - "Planes M0-M3 y decisiones"
Cohesion: 0.11
Nodes (13): Plan M0 Base, Plan M2 Flujo con simuladores, Plan M3 Pagos y seguridad, ScaleIn, SkuIn, TrapIn, TrayIn, scale_enabled() (+5 more)

### Community 12 - "Fondo y color (reconocedor)"
Cohesion: 0.10
Nodes (8): BackgroundModel, color_hist(), crop_zone(), fingerprints(), foreground_regions(), _normalize(), SimilarityDetector, test_crop_zone_cuts_the_frame()

### Community 13 - "Pruebas de la API"
Cohesion: 0.12
Nodes (25): ExplodingService, make(), test_api_docs_are_not_published(), test_cancel_over_http(), test_capture_returns_the_error_instead_of_raising(), test_foreign_origin_is_rejected(), test_full_flow_over_http(), test_help_lifecycle() (+17 more)

### Community 14 - "Componentes UI y formato"
Cohesion: 0.21
Nodes (17): formatPEN(), CancelButton(), Alert(), Confirmar(), Escaneo(), useRecentlyAdded(), Inicio(), Lines() (+9 more)

### Community 15 - "Verificación JWT y pagos"
Cohesion: 0.15
Nodes (15): JwtVerifier, PaymentError, PaymentEvent, sign(), _gateway(), test_hs256_algorithm_confusion_is_rejected(), test_http_gateway_create_and_poll(), test_http_gateway_errors_become_payment_error() (+7 more)

### Community 16 - "Algoritmos de búsqueda (BFS/DFS/A*)"
Cohesion: 0.14
Nodes (15): a_star(), bfs(), Grafo, test_a_star_encuentra_la_combinacion_con_menos_productos(), test_a_star_expande_menos_que_bfs_en_el_flujo(), test_a_star_minimiza_coste(), test_a_star_poda_heuristica_infinita(), test_bfs_minimiza_pasos_no_coste() (+7 more)

### Community 17 - "Registros JSONL"
Cohesion: 0.17
Nodes (14): append(), backup_of(), read_rows(), main(), _mark(), _pct(), report(), summarize() (+6 more)

### Community 18 - "Desconocidos en cámara"
Cohesion: 0.22
Nodes (19): Camera, kiosk(), see(), test_alert_closes_when_the_kiosk_fails(), test_alert_in_w3_records_the_screen(), test_alert_on_cancel_and_next_sale_gets_a_new_one(), test_api_lists_and_resolves_alerts(), test_flooding_alerts_never_hides_a_paid_one() (+11 more)

### Community 19 - "Config TypeScript app"
Cohesion: 0.09
Nodes (22): compilerOptions, allowArbitraryExtensions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection (+14 more)

### Community 20 - "Hoja de ruta y milestones"
Cohesion: 0.13
Nodes (20): Hoja de ruta: Auto-Checkout por visión (MVP), Frentes de trabajo (ia, datos, backend, ui-ux, pagos-seguridad), Hito M0 Base, Hito M1 Datos y modelo, Hito M2 Flujo con simuladores, Hito M3 Pagos y seguridad, Hito M4 Integración con webcam, Hito M5 Demo y medición (+12 more)

### Community 21 - "Utilidades ML y frames"
Cohesion: 0.16
Nodes (10): utf8_output(), extract_frames(), main(), _signature(), test_utf8_output_on_cp1252_console(), make_video(), test_custom_prefix(), test_keeps_only_changes() (+2 more)

### Community 22 - "Problema PesoBandeja"
Cohesion: 0.15
Nodes (4): PesoBandeja, test_estado_aleatorio_respeta_el_maximo(), test_heuristica_es_admisible(), test_hill_climbing_sube_hasta_un_optimo_local()

### Community 23 - "Benchmark de latencia"
Cohesion: 0.17
Nodes (12): Riesgo de latencia RNF-01 (≤150 ms), letterbox(), main(), measure(), Stats, FakeClock, test_letterbox_shape_and_padding(), test_measure_fails_target() (+4 more)

### Community 24 - "Pasarela de pago y seguridad"
Cohesion: 0.14
Nodes (6): Seguridad: JWT RS256, jti y TLS 1.3, Charge, HttpGateway, PaymentGateway, tls13_context(), mock-gateway (pasarela simulada FastAPI, HTTPS 8443)

### Community 25 - "Problema FlujoCompra"
Cohesion: 0.19
Nodes (7): alcanzables(), FlujoCompra, _llega(), sin_salida(), State, test_no_se_puede_confirmar_con_cuatro_productos_ni_pagar_desde_w1(), test_todos_los_estados_alcanzables_tienen_salida()

### Community 26 - "Mock gateway app"
Cohesion: 0.16
Nodes (10): ChargeIn, create_app(), confirm(), create_charge(), find(), get_charge(), pay_page(), require_key() (+2 more)

### Community 27 - "Panel de caja"
Cohesion: 0.18
Nodes (18): request(), useKioskState(), beep(), CajaPanel(), HelpRequest, hhmm(), readSound(), Receipt (+10 more)

### Community 28 - "Flujo W1-W4 y fusión de peso"
Cohesion: 0.18
Nodes (8): Flujo de pantallas W1 a W4, Fusión sensorial visión + peso (±5 g), build_cart(), Cart, CartLine, ScaleReader, Detector, test_build_cart_is_exact()

### Community 29 - "POS simulado y ventas"
Cohesion: 0.19
Nodes (9): SimulatedPos, test_continues_numbering_after_restart(), test_issues_numbered_receipts_and_appends_jsonl(), test_without_file_keeps_receipts_in_memory(), stamp(), test_api_sales_endpoint(), test_sales_today_counts_only_today_newest_first(), test_sales_today_defaults_to_the_local_date() (+1 more)

### Community 30 - "package.json UI"
Cohesion: 0.11
Nodes (16): name, private, type, version, jsdom, oxlint, @stryker-mutator/core, @testing-library/jest-dom (+8 more)

### Community 31 - "Config Stryker"
Cohesion: 0.11
Nodes (18): commandRunner, command, concurrency, coverageAnalysis, htmlReporter, fileName, jsonReporter, fileName (+10 more)

### Community 32 - "TAREAS Criterio 2 - Búsqueda"
Cohesion: 0.18
Nodes (17): Tarea: BFS, DFS, A* y Hill Climbing implementados, Tarea: documento BUSQUEDA.md, Tarea: demo comparativa de búsqueda, Tarea: espacios de estados W1-W4 y bandeja por peso, Tarea: Hill Climbing para afinar KIOSK_THRESHOLD, Tarea: pruebas del módulo de búsqueda, A* con heurística admisible, BFS (búsqueda en anchura) (+9 more)

### Community 33 - "Verificador de dataset"
Cohesion: 0.28
Nodes (12): check_dataset(), format_report(), main(), Report, _sha256(), put(), test_bad_extensions_fail(), test_counts_and_ok() (+4 more)

### Community 34 - "TAREAS Criterio 4 - SVM/KNN/DT/Boosting"
Cohesion: 0.16
Nodes (16): Tarea: KNN, SVM, árbol, boosting y Random Forest sobre un mismo dataset, Tarea: tabla comparativa y argumento de ensambles, Tarea: validación cruzada estratificada y GridSearchCV, Galería de 224 referencias (56 fotos, 4 rotaciones), Modelos ONNX dinov2-small y silueta, Pipeline recorte + DINOv2 + color + galería, Resultados del reconocimiento: 91 % (224 px) y 88 % (140 px), Árbol de decisión (+8 more)

### Community 35 - "Pruebas de la UI"
Cohesion: 0.12
Nodes (11): agua, base, Deferred, snap, toDataURL, agua, base, choco (+3 more)

### Community 36 - "Config TypeScript node"
Cohesion: 0.12
Nodes (16): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, noEmit, noFallthroughCasesInSwitch (+8 more)

### Community 37 - "Claves de desarrollo (devkeys)"
Cohesion: 0.22
Nodes (7): main(), _write_private(), write_signing_keys(), write_tls_certs(), keys(), test_signing_keys_roundtrip(), test_tls_cert_issued_by_ca_for_localhost()

### Community 38 - "Arquitectura de cuatro componentes"
Cohesion: 0.18
Nodes (16): Arquitectura de cuatro componentes (monorepo), create_app() (app.py, FastAPI), kiosk-api (cerebro del quiosco), kiosk-ui (interfaz React + Vite), KioskService (service.py), ml (herramientas del dataset), mock-gateway (pasarela simulada), Dependabot (configuración) (+8 more)

### Community 39 - "Informe de cambios de cámara"
Cohesion: 0.14
Nodes (13): Informe de cambios de cámara 2026-10-13, CameraSource (kiosk-api/src/kiosk/vision.py), Ciclo de apertura y cierre de la webcam por estado, Corrección del falso rechazo de Vizzio (foreground_regions), KioskService (kiosk-api/src/kiosk/service.py), SimilarityDetector (kiosk-api/src/kiosk/recognizer.py), YoloOnnxDetector, Medición del reconocimiento por parecido (+5 more)

### Community 40 - "Hill Climbing"
Cohesion: 0.17
Nodes (7): hill_climbing(), hill_climbing_restarts(), LocalResult, test_hill_climbing_respeta_max_steps(), test_hill_climbing_se_queda_en_el_optimo_si_no_hay_mejora(), test_reinicios_escapan_de_un_maximo_local(), test_reinicios_son_reproducibles()

### Community 41 - "Lectura de sensores en hilo"
Cohesion: 0.15
Nodes (12): capture(), safe_tick(), Reading, make_with_camera(), test_camera_confirmation_freezes_the_list_and_ignores_late_frames(), test_camera_keeps_reading_on_w1_and_w2(), test_camera_waits_for_first_registered_product_without_an_initial_alert(), test_cancelling_reopens_the_camera_and_clears_the_list() (+4 more)

### Community 42 - "Interfaces de búsqueda (DFS/Problem)"
Cohesion: 0.20
Nodes (5): dfs(), InformedProblem, Problem, _rebuild(), test_dfs_llega_a_w4_pero_no_garantiza_el_camino_corto()

### Community 43 - "Integración modo cámara"
Cohesion: 0.14
Nodes (6): camera_kiosk(), test_camera_mode_unknown_after_first_product_does_not_block_confirmation(), test_camera_mode_unknown_does_not_unlock_payment_before_first_product(), test_camera_mode_w1_to_w4_one_product_at_a_time(), wait_for(), Webcam

### Community 44 - "Importar fotos del Drive"
Cohesion: 0.20
Nodes (7): _heic_to_jpg(), import_dataset(), main(), sku_from_folder(), put(), test_import_copies_photos_and_skips_extras(), test_sku_from_folder()

### Community 45 - "Label Studio y catálogo ML"
Cohesion: 0.23
Nodes (7): load_skus(), label_config(), main(), test_load_skus_from_repo_catalog(), test_one_label_per_sku_sorted(), test_rectangle_labels_point_to_image(), test_values_are_escaped()

### Community 46 - "Pruebas del mock gateway"
Cohesion: 0.19
Nodes (7): client(), keys(), new_charge(), test_confirm_then_poll_returns_signed_token(), test_create_returns_qr_payload(), test_pay_page_shows_amount(), test_pending_charge_has_no_token()

### Community 47 - "Cargos de la pasarela"
Cohesion: 0.28
Nodes (6): Charge, ChargeStore, sign_payment(), test_mark_paid_unknown_raises(), test_sign_payment_claims(), test_store_create_and_mark_paid()

### Community 48 - "Dependencias de desarrollo UI"
Cohesion: 0.13
Nodes (15): devDependencies, jsdom, oxlint, @playwright/test, @stryker-mutator/core, @testing-library/jest-dom, @testing-library/react, @types/node (+7 more)

### Community 49 - "Entrenamiento YOLO"
Cohesion: 0.21
Nodes (8): Modelo autocaja-416.onnx, evaluate_gate(), main(), train_and_export(), test_gate_exact_target_passes(), test_gate_fails_below_target(), test_gate_passes_above_target(), test_main_without_dataset_returns_1()

### Community 50 - "Sistema de diseño AutoCaja"
Cohesion: 0.21
Nodes (13): DESIGN.md (sistema de diseño AutoCaja), Botón go (placa roja), La placa de carretera (Creative North Star), Paleta rojo, amarillo y blanco, signs.tsx (formas de señal SVG), Tipografía Overpass, Escala con cqw (ancho del quiosco), Superficie Impeccable: Quiosco del cliente (+5 more)

### Community 51 - "Pruebas e2e Playwright"
Cohesion: 0.16
Nodes (5): RECEIPTS, State, env, REPO, @playwright/test

### Community 52 - "Registro de sesiones"
Cohesion: 0.33
Nodes (7): SessionRecorder, test_memory_keeps_only_the_latest(), test_recorder_accepts_known_notes(), test_recorder_ignores_notes_and_finish_without_session(), test_recorder_tracks_one_session_and_appends_jsonl(), test_session_records_whether_weight_was_checked(), test_report_without_cancellations_and_old_rows()

### Community 53 - "Dobles de prueba (fakes)"
Cohesion: 0.18
Nodes (8): FakeGateway, test_sim_scale_can_be_switched_only_on_w1(), BrokenCamera, FakeClock, make_without_scale(), test_confirmed_camera_purchase_still_checks_scale_without_reading_camera(), test_session_ends_as_fault_when_sensor_fails(), test_without_scale_other_rules_still_apply()

### Community 54 - "Cliente API de la UI"
Cohesion: 0.29
Nodes (8): isLine(), isNum(), isObj(), isSnapshot(), SCREENS, Snapshot, ok, SCREEN_NAME

### Community 55 - "App y Kiosk (UI)"
Cohesion: 0.27
Nodes (10): App(), KioskLive(), Kiosk(), Route(), Screen(), STEP_OF, STEPS, FueraDeServicio() (+2 more)

### Community 56 - "Pruebas de paneles"
Cohesion: 0.18
Nodes (5): alertRoutes, FakeSocket, noSales, Route, snap

### Community 57 - "TAREAS Criterio 1 - Cloud y DevOps"
Cohesion: 0.29
Nodes (12): Bloqueo: Docker no instalado, CD sin probar, Tarea: documento CLOUD_DEVOPS.md, Tarea: Dockerfiles y docker-compose, Tarea: workflow de CD (GHCR y Render), CI actual en GitHub Actions, Cloud Computing (IaaS, PaaS, SaaS), DevOps: ciclo plan-código-CI-CD-operación-monitoreo, Edge frente a cloud (+4 more)

### Community 58 - "POS y paquete kiosk"
Cohesion: 0.25
Nodes (4): test_does_not_rotate_below_the_limit(), test_read_rows_of_missing_file_is_empty(), test_receipt_numbers_survive_rotation(), test_rotates_past_the_limit_and_keeps_one_backup()

### Community 59 - "Decisiones de producto (ayuda, sin balanza)"
Cohesion: 0.24
Nodes (11): Botón de ayuda, Paneles del equipo (/sim, /caja), Decisión: sin balanza por ahora (2026-10-10), SOLICITAR AYUDA, Alertas de seguridad, Balanza opcional (KIOSK_SCALE), Sesiones, boletas y métricas (JSONL), Probar el sistema (modo simulado) (+3 more)

### Community 60 - "README y reconocimiento por galería"
Cohesion: 0.20
Nodes (10): Tablero de productos y banda TOTAL, recognizer.py (reconocimiento por galería), Decisión: reconocimiento por parecido sin entrenar (2026-10-12), Job CI e2e (Playwright), Herramientas del dataset (ml/), Modo cámara, Pruebas de punta a punta (Playwright), Reconocimiento por parecido (galería, DINOv2 y color) (+2 more)

### Community 61 - "Documento informativo"
Cohesion: 0.22
Nodes (11): Documento informativo del proyecto, Catálogo de 11 productos, fusion.py (peso ±5 g), Radiografía del código (graphify), Metas del SRS (ON-01..03, RNF-01..06), Riesgos conocidos, Estado del proyecto (traspaso), Hitos M0 a M5 (+3 more)

### Community 62 - "Filtro de estabilidad"
Cohesion: 0.35
Nodes (5): StabilityFilter, test_change_restarts_count(), test_empty_tray_is_stable_too(), test_needs_three_equal_frames(), test_reset_forgets_history()

### Community 63 - "TAREAS Criterio 5 - Sustentación"
Cohesion: 0.22
Nodes (10): Informe de resultados de la demo (M5, plantilla), Tabla de metas frente al SRS, Reglas de trabajo del equipo, Tarea: guion de sustentación, Tarea: limpieza final (ruff, mypy, suite verde), Tarea: documento TRADEOFFS.md, Criterio 5: Sustentación y Código, ON-01 Reducción de tiempo de cobro (+2 more)

### Community 64 - "TAREAS Criterio 3 - Regresión y clasificación"
Cohesion: 0.29
Nodes (10): Bloqueo: fotos de productos fuera de git, Tarea: dataset tabular desde fotos y catálogo, Tarea: regresión lineal (peso desde tamaño), Tarea: regresión logística conocido/desconocido, Tarea: regresión no lineal (polinómica, Ridge/Lasso), Tarea: explicar regresión frente a clasificación, Regresión lineal: peso desde área de bbox, Regresión logística: producto conocido o desconocido (+2 more)

### Community 65 - "Errores y recalibración"
Cohesion: 0.22
Nodes (4): TransitionError, settle(), test_remove_takes_one_unit_off_the_list(), test_weight_mismatch_blocks_payment()

### Community 66 - "Botón de ayuda UI"
Cohesion: 0.28
Nodes (6): post(), HelpButton(), HelpGlyph(), @fontsource/overpass, react, react-dom

### Community 67 - "Guía del equipo y plan APF3"
Cohesion: 0.29
Nodes (6): Guía del equipo (camino a la máxima nota), Grafo del proyecto (graphify-out), Tablero de estado 2026-11-16, Plan APF 3, Orden de fases 1 a 5, Rúbrica APF 3

### Community 68 - "Reglas clave y pantallas"
Cohesion: 0.29
Nodes (7): Cancelar compra, Escaneo en vivo, uno por uno (W2), Ruta (cuatro discos), Señal de velocidad (cuenta regresiva), Lectura de sensores en otro hilo (threaded_sensing), Reglas clave del backend, Flujo W1 Inicio, W2 Escaneo, W3 Confirmar, QR, W4 Ticket

### Community 69 - "Calidad y mutación"
Cohesion: 0.33
Nodes (6): Plan de calidad (auditoría y fases 1-3), Pruebas de mutación (mutmut 90 %, Stryker 84 %), TypeScript se queda en 6, Workflow Mutación (semanal), Job mutmut (backend), Job Stryker (UI)

### Community 70 - "Entrenamiento y benchmark ML"
Cohesion: 0.38
Nodes (6): Benchmark de latencia (RNF-01), Entrenamiento del reconocedor YOLO, Meta mAP50 >= 0,90, Reparto 70/20/10 con mltools.split, Guía de etiquetado (Label Studio), Label Studio

### Community 71 - "CLI comparativa de búsqueda"
Cohesion: 0.43
Nodes (4): SearchResult, main(), _row(), test_cli_imprime_la_comparacion()

### Community 73 - "Scripts npm"
Cohesion: 0.29
Nodes (7): scripts, build, dev, e2e, lint, preview, test

### Community 74 - "Config oxlint"
Cohesion: 0.33
Nodes (5): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema

### Community 75 - "Dependencias UI"
Cohesion: 0.40
Nodes (5): dependencies, @fontsource/overpass, qrcode, react, react-dom

## Ambiguous Edges - Review These
- `Señal de velocidad (cuenta regresiva)` → `Probar el sistema (modo simulado)`  [AMBIGUOUS]
  DESIGN.md · relation: conceptually_related_to

## Knowledge Gaps
- **64 isolated node(s):** `kiosk`, `@stryker-mutator/core`, `@types/node`, `@types/qrcode`, `@types/react` (+59 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 444 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Plan M0 Base` connect `Planes M0-M3 y decisiones` to `Arquitectura de cuatro componentes`, `Catálogo de productos`, `Hoja de ruta y milestones`, `Flujo W1-W4 y fusión de peso`, `Filtro de estabilidad`?**
  _High betweenness centrality (0.229) - this node is a cross-community bridge._
- **Are the 36 inferred relationships involving `KioskService` (e.g. with `capture()` and `create_app()`) actually correct?**
  _`KioskService` has 36 INFERRED edges - model-reasoned connections that need verification._
- **What connects `kiosk`, `@stryker-mutator/core`, `@types/node` to the rest of the system?**
  _64 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Máquina de estados Checkout` be split into smaller, more focused modules?**
  _Cohesion score 0.08627450980392157 - nodes in this community are weakly interconnected._
- **Why does `Workflow CI` connect `Arquitectura de cuatro componentes` to `Planes M0-M3 y decisiones`, `README y reconocimiento por galería`, `Calidad y mutación`?**
  _High betweenness centrality (0.224) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `create_app()` (e.g. with `lifespan()` and `TransitionError`) actually correct?**
  _`create_app()` has 6 INFERRED edges - model-reasoned connections that need verification._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Señal de velocidad (cuenta regresiva)` and `Probar el sistema (modo simulado)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._