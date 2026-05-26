import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const {
  AlignmentType,
  BorderStyle,
  Document,
  Header,
  HeadingLevel,
  ImageRun,
  Packer,
  PageBreak,
  Paragraph,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
} = await loadDocxModule();

const [contextPath, outputPath, headerImagePath] = process.argv.slice(2);

if (!contextPath || !outputPath) {
  throw new Error("Usage: node build_word_report.mjs <context.json> <output.docx> <header-image>");
}

const context = JSON.parse(await fs.readFile(contextPath, "utf8"));
const headerExists = headerImagePath ? await fileExists(headerImagePath) : false;
const headerImageData = headerExists ? await fs.readFile(headerImagePath) : null;
const headerImageType = headerExists ? detectImageType(headerImagePath) : undefined;

const accentBlue = "1157A7";
const accentGreen = "2F6B5F";

const sections = [
  {
    headers: headerExists
      ? {
          default: new Header({
            children: [
              new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [
                  new ImageRun({
                    data: headerImageData,
                    type: headerImageType,
                    transformation: { width: 930, height: 70 },
                  }),
                ],
              }),
            ],
          }),
        }
      : {},
    properties: {
      page: {
        margin: {
          top: 900,
          bottom: 820,
          left: 850,
          right: 850,
        },
      },
    },
    children: buildDocumentChildren(context, accentBlue, accentGreen),
  },
];

const document = new Document({ sections });
const buffer = await Packer.toBuffer(document);
await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.writeFile(outputPath, buffer);

function buildDocumentChildren(context, accentBlue, accentGreen) {
  const children = [];

  children.push(
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 120 },
      children: [
        new TextRun({
          text: "KTU Result Analysis Report",
          bold: true,
          size: 34,
          color: accentBlue,
        }),
      ],
    })
  );

  children.push(
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 180 },
      children: [
        new TextRun({ text: context.batch.name, bold: true, size: 24 }),
        new TextRun({ text: `\n${context.batch.exam_name}`, size: 22 }),
        ...(context.batch.institution
          ? [new TextRun({ text: `\n${context.batch.institution}`, size: 22 })]
          : []),
      ],
    })
  );

  children.push(
    new Paragraph({
      spacing: { after: 160 },
      children: [
        new TextRun({
          text: `GPA threshold used in this report: greater than ${context.threshold.toFixed(2)}`,
          size: 22,
        }),
      ],
    })
  );

  children.push(sectionHeading("Summary"));
  children.push(
    makeTable(
      [
        ["Batch Name", context.batch.name],
        ["Exam Name", context.batch.exam_name],
        ["Institution", context.batch.institution || "Institution not detected"],
        ["Total Students", String(context.summary.total_students)],
        ["Total Departments", String(context.summary.total_departments)],
        ["Total Courses", String(context.summary.total_courses)],
        ["Average GPA", context.summary.average_gpa.toFixed(2)],
        ["Highest GPA", context.summary.highest_gpa.toFixed(2)],
        ["Lowest GPA", context.summary.lowest_gpa.toFixed(2)],
        ["Students with GPA > threshold", String(context.threshold_students.length)],
      ],
      null,
      accentGreen
    )
  );

  children.push(new Paragraph({ children: [new PageBreak()] }));
  children.push(sectionHeading("Subject-wise Pass Percentage"));
  children.push(
    makeTable(
      context.subjects.map((subject) => [
        subject.department_name,
        subject.course_code,
        subject.course_name,
        String(subject.appeared_count),
        String(subject.passed_count),
        String(subject.failed_count),
        String(subject.absent_count),
        subject.pass_percentage.toFixed(2),
      ]),
      ["Department", "Course Code", "Course Name", "Appeared", "Passed", "Failed", "Absent", "Pass %"],
      accentGreen
    )
  );

  children.push(new Paragraph({ children: [new PageBreak()] }));
  children.push(sectionHeading("Top 10 Ranks in Each Department"));
  const rankingsByDepartment = groupBy(context.department_rankings, "department_name");
  for (const departmentName of Object.keys(rankingsByDepartment).sort()) {
    children.push(subHeading(departmentName));
    children.push(
      makeTable(
        rankingsByDepartment[departmentName].map((row) => [
          String(row.rank),
          row.register_no,
          row.gpa.toFixed(2),
          String(row.passed_count),
          String(row.failed_count),
        ]),
        ["Rank", "Register No", "GPA", "Passed", "Failed"],
        accentGreen
      )
    );
  }

  children.push(new Paragraph({ children: [new PageBreak()] }));
  children.push(sectionHeading("Students Who Failed"));
  children.push(
    makeTable(
      (context.failed_students.length ? context.failed_students : [
        { department_name: "No failed students found", register_no: "", gpa: "", failed_subjects_text: "" },
      ]).map((row) => [
        row.department_name,
        row.register_no,
        row.gpa === "" ? "" : row.gpa.toFixed(2),
        row.failed_subjects_text,
      ]),
      ["Department", "Register No", "GPA", "Failed Subjects"],
      accentGreen
    )
  );

  children.push(new Paragraph({ children: [new PageBreak()] }));
  children.push(sectionHeading(`Students with GPA Greater Than ${context.threshold.toFixed(2)}`));
  children.push(
    new Paragraph({
      spacing: { after: 100 },
      children: [new TextRun({ text: `Overall count: ${context.threshold_students.length} students`, size: 22 })],
    })
  );
  children.push(
    makeTable(
      (context.threshold_counts.length ? context.threshold_counts : [
        { department_name: "No students exceed the threshold", count: 0 },
      ]).map((row) => [row.department_name, String(row.count)]),
      ["Department", "Count"],
      accentGreen
    )
  );
  children.push(new Paragraph({ spacing: { after: 80 } }));
  children.push(
    makeTable(
      (context.threshold_students.length ? context.threshold_students : [
        { register_no: "No students exceed the threshold", department_name: "", gpa: "" },
      ]).map((row) => [
        row.register_no,
        row.department_name,
        row.gpa === "" ? "" : row.gpa.toFixed(2),
      ]),
      ["Register No", "Department", "GPA"],
      accentGreen
    )
  );

  return children;
}

function sectionHeading(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 120, after: 120 },
    children: [new TextRun({ text, bold: true, color: "D34040", size: 28 })],
  });
}

function subHeading(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 120, after: 80 },
    children: [new TextRun({ text, bold: true, color: "1157A7", size: 24 })],
  });
}

function makeTable(rows, headers, accentGreen) {
  const tableRows = [];
  if (headers) {
    tableRows.push(
      new TableRow({
        tableHeader: true,
        children: headers.map((header) =>
          new TableCell({
            shading: { fill: accentGreen },
            borders: uniformBorders(),
            children: [
              new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [new TextRun({ text: header, bold: true, color: "FFFFFF", size: 20 })],
              }),
            ],
          })
        ),
      })
    );
  }

  for (const row of rows) {
    tableRows.push(
      new TableRow({
        children: row.map((value) =>
          new TableCell({
            borders: uniformBorders(),
            children: [
              new Paragraph({
                spacing: { after: 0 },
                children: [new TextRun({ text: String(value ?? ""), size: 19 })],
              }),
            ],
          })
        ),
      })
    );
  }

  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: tableRows,
  });
}

function uniformBorders() {
  return {
    top: { style: BorderStyle.SINGLE, size: 1, color: "D1D9E0" },
    bottom: { style: BorderStyle.SINGLE, size: 1, color: "D1D9E0" },
    left: { style: BorderStyle.SINGLE, size: 1, color: "D1D9E0" },
    right: { style: BorderStyle.SINGLE, size: 1, color: "D1D9E0" },
  };
}

function groupBy(rows, key) {
  return rows.reduce((grouped, row) => {
    const value = row[key];
    grouped[value] ||= [];
    grouped[value].push(row);
    return grouped;
  }, {});
}

async function fileExists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function loadDocxModule() {
  try {
    return await import("docx");
  } catch (error) {
    const candidates = [];
    if (process.env.RESULT_ANALYSER_NODE_MODULES) {
      candidates.push(path.join(process.env.RESULT_ANALYSER_NODE_MODULES, "docx", "dist", "index.mjs"));
    }

    for (const candidate of candidates) {
      if (await fileExists(candidate)) {
        return import(pathToFileURL(candidate).href);
      }
    }

    throw error;
  }
}

function detectImageType(filePath) {
  const extension = path.extname(filePath).toLowerCase();
  if (extension === ".png") {
    return "png";
  }
  if (extension === ".jpg" || extension === ".jpeg") {
    return "jpg";
  }
  if (extension === ".gif") {
    return "gif";
  }
  if (extension === ".bmp") {
    return "bmp";
  }
  if (extension === ".svg") {
    return "svg";
  }
  return "png";
}
