const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, WidthType, BorderStyle, ShadingType,
  LevelFormat, Header, Footer, PageNumber, ImageRun
} = require('docx');

const root = path.resolve(__dirname, '..');
const source = path.join(root, 'docs', 'TISP第一轮机械筛查汇报文档.md');
const output = path.join(root, 'docs', 'TISP第一轮机械筛查汇报文档.docx');
const markdown = fs.readFileSync(source, 'utf8');
const lines = markdown.split(/\r?\n/);

function plain(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\[(.*?)\]\([^)]*\)/g, '$1')
    .trim();
}

function para(text, options = {}) {
  return new Paragraph({
    ...options,
    children: [new TextRun({ text: plain(text), font: 'Microsoft YaHei', size: options.size || 22 })]
  });
}

const borders = {
  top: { style: BorderStyle.SINGLE, size: 1, color: 'C9D2DC' },
  bottom: { style: BorderStyle.SINGLE, size: 1, color: 'C9D2DC' },
  left: { style: BorderStyle.SINGLE, size: 1, color: 'C9D2DC' },
  right: { style: BorderStyle.SINGLE, size: 1, color: 'C9D2DC' },
};

function makeTable(rows) {
  const cols = Math.max(...rows.map(r => r.length));
  const tableWidth = 9746;
  const base = Math.floor(tableWidth / cols);
  const widths = Array.from({ length: cols }, (_, i) => i === cols - 1 ? tableWidth - base * (cols - 1) : base);
  return new Table({
    width: { size: tableWidth, type: WidthType.DXA },
    columnWidths: widths,
    rows: rows.map((row, rowIndex) => new TableRow({
      children: widths.map((width, i) => new TableCell({
        borders,
        width: { size: width, type: WidthType.DXA },
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        shading: rowIndex === 0 ? { fill: 'DCE6F1', type: ShadingType.CLEAR } : undefined,
        children: [new Paragraph({
          children: [new TextRun({
            text: plain(row[i] || ''),
            font: 'Microsoft YaHei',
            size: 19,
            bold: rowIndex === 0,
          })]
        })]
      }))
    }))
  });
}

const children = [];
let i = 0;
let inCode = false;
while (i < lines.length) {
  const line = lines[i];
  if (line.trim() === '```') {
    inCode = !inCode;
    i += 1;
    continue;
  }
  if (inCode) {
    children.push(new Paragraph({
      shading: { fill: 'F3F5F7', type: ShadingType.CLEAR },
      children: [new TextRun({ text: line, font: 'Consolas', size: 18 })]
    }));
    i += 1;
    continue;
  }
  if (line.trim() === '' || line.trim() === '---') {
    i += 1;
    continue;
  }
  if (line.startsWith('|')) {
    const rows = [];
    while (i < lines.length && lines[i].startsWith('|')) {
      const cells = lines[i].split('|').slice(1, -1).map(x => x.trim());
      if (!cells.every(x => /^:?-{3,}:?$/.test(x))) rows.push(cells);
      i += 1;
    }
    if (rows.length) children.push(makeTable(rows));
    continue;
  }
  if (line.startsWith('# ')) {
    children.push(new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 360 },
      children: [new TextRun({ text: plain(line.slice(2)), font: 'Microsoft YaHei', size: 36, bold: true })]
    }));
    const flowchart = 'D:\\xwechat_files\\wxid_nkd2y5sf7wih22_bcf7\\temp\\RWTemp\\2026-07\\c9275057d5983edcc5baf3944633ad09\\f231ed399ed7511f5b9f9141a71ef87a.png';
    if (fs.existsSync(flowchart)) {
      children.push(new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new ImageRun({
          type: 'png',
          data: fs.readFileSync(flowchart),
          transformation: { width: 500, height: 274 },
          altText: { title: '问卷筛查流程图', description: '自动机械筛查与人工复核流程', name: 'screening-flowchart' }
        })]
      }));
      children.push(new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: '图：本项目采用“自动机械筛查—人工复核—最终分类”的总体流程', font: 'Microsoft YaHei', size: 17, color: '666666' })]
      }));
    }
    i += 1;
    continue;
  }
  if (line.startsWith('### ')) {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun({ text: plain(line.slice(4)), font: 'Microsoft YaHei' })] }));
    i += 1;
    continue;
  }
  if (line.startsWith('## ')) {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: plain(line.slice(3)), font: 'Microsoft YaHei' })] }));
    i += 1;
    continue;
  }
  if (line.startsWith('- ')) {
    children.push(new Paragraph({
      numbering: { reference: 'bullets', level: 0 },
      children: [new TextRun({ text: plain(line.slice(2)), font: 'Microsoft YaHei', size: 22 })]
    }));
    i += 1;
    continue;
  }
  children.push(para(line, { spacing: { after: 140, line: 300 } }));
  i += 1;
}

const doc = new Document({
  numbering: {
    config: [{
      reference: 'bullets',
      levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } }]
    }]
  },
  styles: {
    default: { document: { run: { font: 'Microsoft YaHei', size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: 'Microsoft YaHei', size: 30, bold: true, color: '1F4E79' },
        paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: 'Microsoft YaHei', size: 26, bold: true, color: '2F75B5' },
        paragraph: { spacing: { before: 260, after: 140 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: 'Microsoft YaHei', size: 24, bold: true, color: '5B9BD5' },
        paragraph: { spacing: { before: 180, after: 100 }, outlineLevel: 2 } },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 }
      }
    },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: 'TISP 第一轮机械筛查方案', font: 'Microsoft YaHei', size: 16, color: '7F8C8D' })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: '第 ', font: 'Microsoft YaHei', size: 16 }), new TextRun({ children: [PageNumber.CURRENT], font: 'Microsoft YaHei', size: 16 }), new TextRun({ text: ' 页', font: 'Microsoft YaHei', size: 16 })] })] }) },
    children
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(output, buffer);
  console.log(output);
});
