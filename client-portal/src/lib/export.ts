"use client";

export async function exportToCSV(data: Record<string, unknown>[], filename: string) {
  const Papa = (await import("papaparse")).default;
  const csv = Papa.unparse(data);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${filename}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}

export async function exportToPDF(
  data: Record<string, unknown>[],
  filename: string,
  title: string
) {
  const { default: jsPDF } = await import("jspdf");
  const { default: autoTable } = await import("jspdf-autotable");

  const doc = new jsPDF();

  // Title
  doc.setFontSize(18);
  doc.setTextColor(108, 99, 255);
  doc.text(title, 14, 22);

  // Date
  doc.setFontSize(10);
  doc.setTextColor(128, 128, 128);
  doc.text(`Generated: ${new Date().toLocaleDateString()}`, 14, 30);

  if (data.length > 0) {
    const columns = Object.keys(data[0]);
    const rows = data.map((row) => columns.map((col) => String(row[col] ?? "")));

    autoTable(doc, {
      head: [columns],
      body: rows,
      startY: 36,
      styles: { fontSize: 9, cellPadding: 3 },
      headStyles: {
        fillColor: [108, 99, 255],
        textColor: [255, 255, 255],
        fontStyle: "bold",
      },
      alternateRowStyles: { fillColor: [245, 245, 250] },
    });
  }

  doc.save(`${filename}.pdf`);
}
