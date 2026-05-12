// Build the Pill Detection System Status Report as a Word .docx
const fs = require('fs');
const path = require('path');

// Use the globally installed docx package
const NODE_GLOBAL = 'C:/Users/jaime/AppData/Roaming/npm/node_modules';
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, PageOrientation, LevelFormat,
  TabStopType, TabStopPosition, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber, PageBreak
} = require(path.join(NODE_GLOBAL, 'docx'));

// ── Helpers ──────────────────────────────────────────────────────────────────
const cellBorder = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const cellBorders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };
const cellMargins = { top: 100, bottom: 100, left: 140, right: 140 };

function P(text, opts = {}) {
  const runs = Array.isArray(text)
    ? text
    : [new TextRun({ text, font: "Calibri", size: 22, ...opts.run })];
  return new Paragraph({
    children: runs,
    spacing: opts.spacing || { after: 120, line: 300 },
    ...opts.paragraph,
  });
}

function H1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text, bold: true, size: 32, color: "1F4E79", font: "Calibri" })],
    spacing: { before: 360, after: 180 },
  });
}

function H2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text, bold: true, size: 26, color: "2E75B6", font: "Calibri" })],
    spacing: { before: 240, after: 140 },
  });
}

function tableCell(text, opts = {}) {
  const isHeader = opts.header === true;
  const runs = Array.isArray(text) ? text : [new TextRun({
    text, font: "Calibri", size: 20,
    bold: isHeader, color: isHeader ? "FFFFFF" : "1A1A1A",
  })];
  return new TableCell({
    borders: cellBorders,
    margins: cellMargins,
    width: { size: opts.width, type: WidthType.DXA },
    shading: { fill: isHeader ? "1F4E79" : (opts.alt ? "F2F6FB" : "FFFFFF"), type: ShadingType.CLEAR },
    children: [new Paragraph({ children: runs, spacing: { after: 0 } })],
  });
}

function tableRow(cells, widths, opts = {}) {
  return new TableRow({
    children: cells.map((c, i) => tableCell(c, { ...opts, width: widths[i] })),
  });
}

function buildTable(headers, rows, columnWidths) {
  return new Table({
    width: { size: columnWidths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths,
    rows: [
      new TableRow({
        tableHeader: true,
        children: headers.map((h, i) =>
          tableCell(h, { header: true, width: columnWidths[i] })),
      }),
      ...rows.map((r, idx) =>
        tableRow(r, columnWidths, { alt: idx % 2 === 0 })),
    ],
  });
}

function bullet(text, runs) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    spacing: { after: 80 },
    children: runs || [new TextRun({ text, font: "Calibri", size: 22 })],
  });
}

// Inline run helpers
const t = (text, opts = {}) => new TextRun({ text, font: "Calibri", size: 22, ...opts });
const b = (text) => t(text, { bold: true });
const code = (text) => new TextRun({ text, font: "Consolas", size: 20, color: "8B0000" });

// ── Document ─────────────────────────────────────────────────────────────────
const doc = new Document({
  creator: "Jaime Medina",
  title: "Hero Smart Pill Dispenser — Pill Detection System Status Report",
  styles: {
    default: { document: { run: { font: "Calibri", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Calibri", color: "1F4E79" },
        paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Calibri", color: "2E75B6" },
        paragraph: { spacing: { before: 240, after: 140 }, outlineLevel: 1 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
      { reference: "numbers",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },           // US Letter
        margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 }, // 0.75"
      },
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        alignment: AlignmentType.RIGHT,
        children: [new TextRun({ text: "Hero Smart Pill Dispenser  ·  Detection Status Report",
                                 font: "Calibri", size: 18, color: "808080" })],
      })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({ text: "Page ", font: "Calibri", size: 18, color: "808080" }),
          new TextRun({ children: [PageNumber.CURRENT], font: "Calibri", size: 18, color: "808080" }),
          new TextRun({ text: " of ", font: "Calibri", size: 18, color: "808080" }),
          new TextRun({ children: [PageNumber.TOTAL_PAGES], font: "Calibri", size: 18, color: "808080" }),
        ],
      })] }),
    },
    children: [
      // ── Title block ─────────────────────────────────────────────────────────
      new Paragraph({
        alignment: AlignmentType.LEFT,
        spacing: { after: 60 },
        children: [new TextRun({
          text: "Hero Smart Pill Dispenser",
          bold: true, size: 36, color: "1F4E79", font: "Calibri",
        })],
      }),
      new Paragraph({
        alignment: AlignmentType.LEFT,
        spacing: { after: 240 },
        children: [new TextRun({
          text: "Pill Detection System — Status Report",
          size: 28, color: "404040", font: "Calibri",
        })],
      }),
      new Paragraph({
        spacing: { after: 360 },
        children: [
          new TextRun({ text: "Author: ", bold: true, font: "Calibri", size: 20, color: "606060" }),
          new TextRun({ text: "Jaime Medina   ", font: "Calibri", size: 20, color: "404040" }),
          new TextRun({ text: "Date: ", bold: true, font: "Calibri", size: 20, color: "606060" }),
          new TextRun({ text: "29 April 2026", font: "Calibri", size: 20, color: "404040" }),
        ],
      }),

      // ── 1. Overview ─────────────────────────────────────────────────────────
      H1("1. System Overview"),
      P([
        t("The Hero Smart Pill Dispenser combines three components that work together as a complete care pipeline: "),
        b("(a)"), t(" a Flask “Raspberry Pi simulator” server hosting a real ML pill-detection pipeline; "),
        b("(b)"), t(" a Flutter mobile app for end-users and caregivers; and "),
        b("(c)"), t(" a Three.js 3D viewer showing the physical Fusion 360 model with live mechanical animation tied to real device events."),
      ]),
      P([
        t("Pill detection — identifying which medication a user has just placed in the chamber — is the project’s main selling point and is the focus of this report."),
      ]),

      // ── 2. ML Pipeline ──────────────────────────────────────────────────────
      H1("2. Detection ML Pipeline (the core)"),
      P([
        t("The detection system uses a "),
        b("hybrid neural + classical"),
        t(" approach to identify pills against the user’s active prescription."),
      ]),
      buildTable(
        ["Component", "Implementation", "File"],
        [
          ["Embedding model",
           "MobileNetV2 ONNX, 1280-dim L2-normalised embeddings, ImageNet normalisation, 224×224 input. ONNX Runtime selects TensorRT → CUDA → CPU automatically.",
           "detection/model.py (EmbeddingModel)"],
          ["Image preprocessing",
           "Perspective correction → Otsu segmentation → bounding-box crop → 224×224 resize. Outputs the tensor plus a 68-dim classical feature vector (HSV histograms + shape descriptors).",
           "detection/preprocess.py"],
          ["Matcher",
           "Hybrid score: 65% neural cosine similarity + 35% classical similarity (chi-squared HSV histograms + L2 shape distance). Thresholds: MATCH ≥ 0.10, UNSURE ≥ 0.04, else NO_MATCH.",
           "detection/model.py (PillMatcher)"],
          ["Profile database",
           "NHI-code-keyed storage: per-pill embedding.npy + classical.npy + reference images. JSON index for metadata.",
           "detection/database.py (PillDatabase)"],
          ["Auto-registration",
           "First 3 captured pills of each medication automatically build the reference profile (mean embedding, mean classical features). From pill 4 onwards matching uses the locked profile.",
           "detection/demo_server.py::_infer_pill_image"],
          ["Cold-start fallback",
           "When no profiles or accumulators exist yet, the system falls back to NHI shape/colour priors from the prescription so detection still produces a reasonable answer on the very first pill.",
           "detection/demo_server.py::_nhi_prior_match"],
        ],
        [2200, 5500, 2700]
      ),
      new Paragraph({ spacing: { before: 180 } }),
      P([
        b("Why this matters: "),
        t("the user does "), b("not"),
        t(" need to pre-photograph reference pills before the demo. The system learns each medication’s profile from the first 3 pills loaded, then matches all subsequent pills against the locked embedding with high confidence."),
      ]),

      // ── 3. Server endpoints ─────────────────────────────────────────────────
      H1("3. Server Endpoints (the “Raspberry Pi” simulator)"),
      P([
        t("Running on the laptop as a stand-in for the real Pi, with persistent state across reboots."),
      ]),
      buildTable(
        ["Endpoint", "Purpose"],
        [
          ["POST /detect",
           "Real ONNX inference. Accepts multipart image + slot. Runs preprocess → embed → match → returns {result, confidence, detected_nhi, detected_name, top_candidates, auto_registered}. Saves the capture for viewer display."],
          ["GET /recent_capture.jpg",
           "Serves the last uploaded pill image to the 3D viewer’s camera mini-window."],
          ["POST /prescription",
           "Loads the user’s medication list into the matcher’s NHI prior database."],
          ["POST /load_pill, POST /dispense",
           "Mechanical sequence triggers (drive 3D animation in the viewer)."],
          ["GET /device_info, POST /reset, POST /app/connect",
           "Pi-like device identity (serial, firmware, uptime), factory reset, app pairing handshake."],
          ["GET /events/recent",
           "Polling endpoint streaming detection + mechanical events to the viewer and the app."],
        ],
        [3000, 7400]
      ),
      new Paragraph({ spacing: { before: 180 } }),
      P([
        t("Device state is persisted to "), code("pi_state.json"),
        t(" so the server behaves like a real device that remembers its loaded slots and paired user across power cycles."),
      ]),

      // ── 4. Flutter App ──────────────────────────────────────────────────────
      H1("4. Flutter App Integration"),
      P([t("The mobile app drives the entire workflow.")]),
      buildTable(
        ["Capability", "Status", "Notes"],
        [
          ["QR-code prescription scan", "Working",
           "mobile_scanner parses Taiwan NHI QR codes; extracts NHI codes, hospital, doctor, medication list with dosage and frequency."],
          ["OCR prescription scan", "Working",
           "google_mlkit_text_recognition for Chinese; falls back to manual entry if OCR confidence is low."],
          ["Manual entry", "Working", "Standard form."],
          ["Auto-send prescription to dispenser", "Working",
           "After save, app POSTs to /prescription if HTTP mode is active."],
          ["Loading Wizard", "Working",
           "Step-by-step guided loading of every medication; pill counter (已裝載 N / Quantity) per medication."],
          ["Pill detection in wizard", "Server-side ready, app camera UI being added",
           "Plan: replace blind “tap Confirm” with phone-camera capture → multipart upload to /detect → branch on MATCH/UNSURE/NO_MATCH."],
          ["Schedule + dose times", "Working",
           "Builds daily schedule from prescription frequency (QD/BID/TID/QID/HS) with default dose times."],
          ["Home dispense flow", "Working",
           "“立即出藥” button when the next dose is overdue or within 30 min; “Did you take it?” confirmation marks the dose as taken in the dose log."],
          ["Live dispenser status banner", "Working",
           "Top-of-home pill chip: 藥盒已連線 / 連線中 / 無法連線 / 藥盒離線 / 模擬模式."],
          ["3D demo trigger from app", "Working",
           "Dispenser status screen launches the full mechanical animation in the 3D viewer."],
          ["Adherence history & tracking", "Working",
           "Hive local cache + Firestore sync."],
          ["Multi-mode connection", "Working",
           "Mock (no hardware), HTTP (laptop server, current demo), BLE (real Pi) — all switchable in setup screen."],
        ],
        [3000, 2200, 5200]
      ),
      new Paragraph({ spacing: { before: 180 } }),
      P([
        t("The Riverpod state pattern keeps prescription / schedule / dispenser providers reactive, so the home screen, wizard, and viewer all update when any layer changes."),
      ]),

      // ── 5. LINE ─────────────────────────────────────────────────────────────
      H1("5. LINE Messaging Integration"),
      P([t("Taiwan-specific user-facing notification channel via LINE Notify.")]),
      buildTable(
        ["Capability", "Status", "File"],
        [
          ["LINE Notify token storage", "Working", "lib/services/line_service.dart"],
          ["Dose reminder push", "Working", "Sends “請服用 [medication]” when a dose fires."],
          ["Adherence reports to caregivers", "Working", "Daily summary push to a paired caregiver’s LINE group."],
          ["Caregiver dashboard", "Working", "Caregivers see real-time adherence status and missed doses."],
          ["LINE settings UI", "Working", "Setup screen in app for token + group binding."],
        ],
        [3000, 1700, 5700]
      ),

      // ── 6. Supporting systems ───────────────────────────────────────────────
      H1("6. Supporting Systems"),
      bullet(null, [
        b("3D digital twin viewer ("),
        code("detection/viewer.html"),
        b("): "),
        t("Three.js render of the actual Fusion 360 GLB. Real component pivots animated by server events. Cutaway transparency reveals internal pill flow during loading and dispensing. “Last Detection” panel + camera mini-window for showing detection results is the next planned addition."),
      ]),
      bullet(null, [
        b("Voice notifications: "),
        t("TTS-based dose reminders for elderly users with low literacy."),
      ]),
      bullet(null, [
        b("Multi-language: "),
        t("Traditional Chinese (primary) + English UI strings throughout."),
      ]),
      bullet(null, [
        b("Persistent device pairing: "),
        t("First app-connect pairs the device to a user ID; survives Pi reboots via "),
        code("pi_state.json"),
        t("."),
      ]),

      // ── 7. End-to-end working ───────────────────────────────────────────────
      H1("7. What’s Working End-to-End Today"),
      new Paragraph({ numbering: { reference: "numbers", level: 0 },
        spacing: { after: 80 },
        children: [t("Open Flutter app → pair to laptop server (acts as the Pi).")] }),
      new Paragraph({ numbering: { reference: "numbers", level: 0 },
        spacing: { after: 80 },
        children: [t("Scan a Taiwan NHI prescription QR code → app extracts medications + NHI codes → auto-pushes to server.")] }),
      new Paragraph({ numbering: { reference: "numbers", level: 0 },
        spacing: { after: 80 },
        children: [t("Server sends prescription into PillDatabase for NHI-prior matching.")] }),
      new Paragraph({ numbering: { reference: "numbers", level: 0 },
        spacing: { after: 80 },
        children: [t("Open Loading Wizard → walk through each medication.")] }),
      new Paragraph({ numbering: { reference: "numbers", level: 0 },
        spacing: { after: 80 },
        children: [
          b("POST /detect with a real pill photo runs the full ONNX pipeline"),
          t(", returns real confidence and NHI code (verified end-to-end with the ePillID test dataset)."),
        ] }),
      new Paragraph({ numbering: { reference: "numbers", level: 0 },
        spacing: { after: 80 },
        children: [t("Auto-registration locks the medication’s reference profile after 3 successful detections.")] }),
      new Paragraph({ numbering: { reference: "numbers", level: 0 },
        spacing: { after: 80 },
        children: [t("Server fires real mechanical events → 3D viewer animates the pill flow with cutaway transparency.")] }),
      new Paragraph({ numbering: { reference: "numbers", level: 0 },
        spacing: { after: 80 },
        children: [t("Dispense flow: home screen “立即出藥” → server runs sequence → “您是否已服用此藥?” dialog marks the dose as taken.")] }),
      new Paragraph({ numbering: { reference: "numbers", level: 0 },
        spacing: { after: 80 },
        children: [t("LINE notifies caregivers of missed doses.")] }),
      new Paragraph({ numbering: { reference: "numbers", level: 0 },
        spacing: { after: 80 },
        children: [
          t("State persists across server reboots in "),
          code("pi_state.json"),
          t(" + auto-registered profiles in "),
          code("data/profiles/"),
          t("."),
        ] }),

      // ── 8. Active work ──────────────────────────────────────────────────────
      H1("8. Active Work"),
      bullet("Flutter camera capture step in the Loading Wizard (replacing the current blind-confirm flow with real image_picker → /detect)."),
      bullet("DetectionResult Freezed model in the app."),
      bullet("Viewer detection panel + camera mini-window showing the real uploaded image and detection result with LED / pill colour driven by MATCH / UNSURE / NO_MATCH."),

      new Paragraph({ spacing: { before: 240 } }),
      P([
        b("Bottom line: "),
        t("the detection backend is the demonstrably real part — reviewers can run "),
        code("curl -F slot=1 -F image=@pill.jpg http://localhost:5000/detect"),
        t(" right now and receive a real ONNX-inference result with measurable confidence, against the user’s active prescription."),
      ]),
    ],
  }],
});

const outPath = "C:/Users/jaime/Documents/pill/Pill_Detection_Status_Report.docx";
Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outPath, buf);
  console.log("Wrote " + outPath + "  (" + buf.length + " bytes)");
});
