import datetime
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from tpm.models import Department, PillarEntry, KPIValue
from tpm.utils.decorators import dept_access_required
from tpm.utils.export import generate_pillar_pdf, generate_pillar_excel
from tpm.utils.kpi_definitions import KPI_DEFINITIONS
from tpm.utils.calculations import compute_achievement

def get_months_list():
    return [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]

@dept_access_required
def report_page(request, dept_id):
    dept = get_object_or_404(Department, id=dept_id)
    today = datetime.date.today()
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))
    
    pillars_meta = [
        ('KK', 'Kobetsu Kaizen'),
        ('JH', 'Jishu Hozen'),
        ('PM', 'Planned Maintenance'),
        ('QM', 'Quality Maintenance'),
        ('ET', 'Education & Training'),
        ('DM', 'Initial Flow Control / Design & Management'),
        ('SHE', 'Safety, Health & Environment'),
        ('OTPM', 'Office TPM')
    ]
    
    report_data = []
    
    # Standard 8 Pillars scores calculation for HTML review
    for code, name in pillars_meta:
        entry = PillarEntry.objects.filter(
            department=dept, pillar=code, month=month, year=year
        ).first()
        
        definitions = KPI_DEFINITIONS.get(code, [])
        kpi_list = []
        achievements = []
        
        for d in definitions:
            db_val = KPIValue.objects.filter(pillar_entry=entry, sl_no=d['sl_no']).first() if entry else None
            
            actual = db_val.actual if db_val else None
            target = db_val.target if db_val else d['target']
            benchmark = db_val.benchmark if db_val else d['benchmark']
            remarks = db_val.remarks if db_val else ''
            
            achievement = None
            status = 'pending'
            if actual is not None and target is not None:
                achievement = compute_achievement(actual, target, d['name'])
                status = 'on-track' if achievement >= 90 else ('at-risk' if achievement >= 75 else 'behind')
                achievements.append(achievement)
                
            kpi_list.append({
                'sl_no': d['sl_no'],
                'name': d['name'],
                'uom': d['uom'],
                'benchmark': benchmark,
                'target': target,
                'actual': actual,
                'achievement': achievement,
                'remarks': remarks,
                'status': status,
            })
            
        avg_achievement = sum(achievements) / len(achievements) if achievements else 0.0
        
        report_data.append({
            'code': code,
            'name': name,
            'kpis': kpi_list,
            'achievement': round(avg_achievement, 1),
            'submitted': entry.submitted_at if entry else None,
            'submitted_by': entry.submitted_by if entry else None,
        })
        
    context = {
        'dept': dept,
        'month': month,
        'year': year,
        'months': get_months_list(),
        'years': range(2025, today.year + 2),
        'report_data': report_data,
        'month_label': dict(get_months_list()).get(month),
    }
    return render(request, 'department/report.html', context)


@dept_access_required
def export_pdf(request, dept_id):
    dept = get_object_or_404(Department, id=dept_id)
    today = datetime.date.today()
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))
    
    pdf_content = generate_pillar_pdf(dept, month, year)
    
    response = HttpResponse(pdf_content, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="TPM_Report_{dept.code}_{year}_{month}.pdf"'
    return response


@dept_access_required
def export_excel(request, dept_id):
    dept = get_object_or_404(Department, id=dept_id)
    today = datetime.date.today()
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))
    
    excel_content = generate_pillar_excel(dept, month, year)
    
    response = HttpResponse(
        excel_content,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="TPM_Report_{dept.code}_{year}_{month}.xlsx"'
    return response
