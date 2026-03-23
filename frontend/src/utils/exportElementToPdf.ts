import { jsPDF } from 'jspdf';
import html2canvas from 'html2canvas';

type PdfOrientation = 'portrait' | 'landscape';

interface ExportElementToPdfOptions {
  element: HTMLElement;
  filename: string;
  title?: string;
  subtitle?: string;
  orientation?: PdfOrientation;
  brandLabel?: string;
}

const waitForFonts = async () => {
  if ('fonts' in document && document.fonts?.ready) {
    try {
      await document.fonts.ready;
    } catch {
      // Ignore font readiness issues and continue with export.
    }
  }
};

const createExportWrapper = (element: HTMLElement, title?: string, subtitle?: string) => {
  const wrapper = document.createElement('div');
  wrapper.style.position = 'fixed';
  wrapper.style.left = '-100000px';
  wrapper.style.top = '0';
  wrapper.style.zIndex = '-1';
  wrapper.style.width = `${Math.max(
    Math.ceil(element.getBoundingClientRect().width),
    element.scrollWidth,
    960,
  )}px`;
  wrapper.style.background = '#ffffff';
  wrapper.style.padding = '28px';
  wrapper.style.boxSizing = 'border-box';
  wrapper.style.fontFamily = 'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
  wrapper.style.color = '#0f172a';

  if (title || subtitle) {
    const header = document.createElement('div');
    header.style.marginBottom = '18px';

    if (title) {
      const titleNode = document.createElement('div');
      titleNode.textContent = title;
      titleNode.style.fontSize = '28px';
      titleNode.style.fontWeight = '700';
      titleNode.style.lineHeight = '1.2';
      header.appendChild(titleNode);
    }

    if (subtitle) {
      const subtitleNode = document.createElement('div');
      subtitleNode.textContent = subtitle;
      subtitleNode.style.marginTop = '6px';
      subtitleNode.style.fontSize = '14px';
      subtitleNode.style.color = '#64748b';
      header.appendChild(subtitleNode);
    }

    wrapper.appendChild(header);
  }

  const clone = element.cloneNode(true) as HTMLElement;
  clone.style.maxWidth = 'none';
  clone.style.width = '100%';
  clone.style.margin = '0';
  wrapper.appendChild(clone);

  return wrapper;
};

export const exportElementToPdf = async ({
  element,
  filename,
  title,
  subtitle,
  orientation = 'portrait',
  brandLabel = 'Taxja',
}: ExportElementToPdfOptions) => {
  await waitForFonts();

  const wrapper = createExportWrapper(element, title, subtitle);
  document.body.appendChild(wrapper);

  try {
    const canvas = await html2canvas(wrapper, {
      backgroundColor: '#ffffff',
      scale: Math.min(window.devicePixelRatio || 1, 2),
      useCORS: true,
      logging: false,
      windowWidth: wrapper.scrollWidth,
      width: wrapper.scrollWidth,
      height: wrapper.scrollHeight,
      scrollX: 0,
      scrollY: 0,
    });

    const pdf = new jsPDF({
      orientation,
      unit: 'mm',
      format: 'a4',
      compress: true,
    });

    const pageWidth = pdf.internal.pageSize.getWidth();
    const pageHeight = pdf.internal.pageSize.getHeight();
    const margin = 10;
    const footerHeight = 8;
    const usableWidth = pageWidth - margin * 2;
    const usableHeight = pageHeight - margin * 2 - footerHeight;
    const pxPerMm = canvas.width / usableWidth;
    const pageHeightPx = Math.max(1, Math.floor(usableHeight * pxPerMm));

    let offsetY = 0;
    let pageIndex = 0;

    while (offsetY < canvas.height) {
      const sliceHeight = Math.min(pageHeightPx, canvas.height - offsetY);
      const pageCanvas = document.createElement('canvas');
      pageCanvas.width = canvas.width;
      pageCanvas.height = sliceHeight;

      const pageCtx = pageCanvas.getContext('2d');
      if (!pageCtx) {
        throw new Error('canvas_context_unavailable');
      }

      pageCtx.fillStyle = '#ffffff';
      pageCtx.fillRect(0, 0, pageCanvas.width, pageCanvas.height);
      pageCtx.drawImage(
        canvas,
        0,
        offsetY,
        canvas.width,
        sliceHeight,
        0,
        0,
        canvas.width,
        sliceHeight,
      );

      if (pageIndex > 0) {
        pdf.addPage();
      }

      const sliceHeightMm = sliceHeight / pxPerMm;
      const sliceDataUrl = pageCanvas.toDataURL('image/png');
      pdf.addImage(sliceDataUrl, 'PNG', margin, margin, usableWidth, sliceHeightMm);

      pdf.setFont('helvetica', 'normal');
      pdf.setFontSize(9);
      pdf.setTextColor(100, 116, 139);
      pdf.text(
        `${brandLabel} - ${new Date().toLocaleDateString()}`,
        margin,
        pageHeight - 4,
      );
      pdf.text(
        `${pageIndex + 1}`,
        pageWidth - margin,
        pageHeight - 4,
        { align: 'right' },
      );

      pageIndex += 1;
      offsetY += sliceHeight;
    }

    pdf.save(filename);
  } finally {
    document.body.removeChild(wrapper);
  }
};

export default exportElementToPdf;
