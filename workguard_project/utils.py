from django.template.loader import get_template
from django.http import HttpResponse
from xhtml2pdf import pisa


def render_to_pdf(template_name, context, filename):
    template = get_template(template_name)
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse("An error occurred while generating the PDF.", status=500)

    return response