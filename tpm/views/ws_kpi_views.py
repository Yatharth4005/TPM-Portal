import json
import datetime
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.contrib import messages
from tpm.models import Department, Workstation, WorkstationKPI, WorkstationValue
from tpm.utils.decorators import dept_access_required

def get_months_list():
    return [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]

@dept_access_required
def ws_kpi_page(request, dept_id):
    dept = get_object_or_404(Department, id=dept_id)
    today = datetime.date.today()
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))
    tab = request.GET.get('tab', 'entry')  # 'entry' or 'analytics'
    
    workstations = Workstation.objects.filter(department=dept).order_by('name')
    
    # Process workstations data for rendering
    ws_list = []
    for ws in workstations:
        kpis_data = []
        for kpi in ws.kpis.all():
            val = WorkstationValue.objects.filter(
                workstation_kpi=kpi, month=month, year=year
            ).first()
            
            actual = val.actual if val else None
            remarks = val.remarks if val else ''
            
            achievement = None
            if actual is not None and kpi.commitment is not None:
                if kpi.goodness_indicator == 'LOWER':
                    achievement = min(100.0, (kpi.commitment / actual) * 100.0) if actual != 0 else 100.0
                else:
                    achievement = (actual / kpi.commitment) * 100.0 if kpi.commitment != 0 else 100.0

            kpis_data.append({
                'id': kpi.id,
                'kpi_name': kpi.kpi_name,
                'uom': kpi.uom,
                'goodness_indicator': kpi.goodness_indicator,
                'baseline': kpi.baseline,
                'commitment': kpi.commitment,
                'actual': actual,
                'remarks': remarks,
                'achievement': achievement,
            })
            
        ws_list.append({
            'id': ws.id,
            'name': ws.name,
            'leader': ws.leader,
            'inception_date': ws.inception_date,
            'kpis': kpis_data,
        })
        
    # Analytics Tab Processing
    analytics_data = {}
    if tab == 'analytics':
        selected_ws_id = request.GET.get('workstation_id')
        selected_ws = None
        if selected_ws_id:
            selected_ws = workstations.filter(id=selected_ws_id).first()
        if not selected_ws and workstations.exists():
            selected_ws = workstations.first()
            
        if selected_ws:
            # Monthly actuals vs commitments trend (last 12 months)
            months_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            ws_trends = {}
            for kpi in selected_ws.kpis.all():
                ws_trends[kpi.id] = {
                    'name': kpi.kpi_name,
                    'uom': kpi.uom,
                    'baseline': kpi.baseline,
                    'commitment': kpi.commitment,
                    'goodness': kpi.goodness_indicator,
                    'actuals': [],
                }
                for m in range(1, 13):
                    val = WorkstationValue.objects.filter(
                        workstation_kpi=kpi, month=m, year=year
                    ).first()
                    ws_trends[kpi.id]['actuals'].append(val.actual if val else None)
            
            analytics_data = {
                'selected_ws_id': selected_ws.id,
                'selected_ws_name': selected_ws.name,
                'ws_trends_json': json.dumps(ws_trends),
                'months_labels_json': json.dumps(months_labels),
            }

    context = {
        'dept': dept,
        'month': month,
        'year': year,
        'months': get_months_list(),
        'years': range(2025, today.year + 2),
        'workstations': workstations,
        'ws_list': ws_list,
        'tab': tab,
        'analytics_data': analytics_data,
        'month_label': dict(get_months_list()).get(month),
    }
    return render(request, 'department/ws_kpi.html', context)


@dept_access_required
@require_POST
def save_workstation(request, dept_id, ws_id):
    dept = get_object_or_404(Department, id=dept_id)
    ws = get_object_or_404(Workstation, id=ws_id, department=dept)
    month = int(request.GET.get('month'))
    year = int(request.GET.get('year'))
    
    # Save all inputs for the given workstation
    kpis_data = []
    for kpi in ws.kpis.all():
        actual_field = f"actual_{kpi.id}"
        remarks_field = f"remarks_{kpi.id}"
        
        actual_str = request.POST.get(actual_field)
        remarks = request.POST.get(remarks_field, '').strip()
        
        val, created = WorkstationValue.objects.get_or_create(
            workstation_kpi=kpi, month=month, year=year
        )
        
        val.actual = float(actual_str) if actual_str else None
        val.remarks = remarks
        val.save()
        
        # Calculate achievement
        achievement = None
        if val.actual is not None and kpi.commitment is not None:
            if kpi.goodness_indicator == 'LOWER':
                achievement = min(100.0, (kpi.commitment / val.actual) * 100.0) if val.actual != 0 else 100.0
            else:
                achievement = (val.actual / kpi.commitment) * 100.0 if kpi.commitment != 0 else 100.0
                
        kpis_data.append({
            'id': kpi.id,
            'kpi_name': kpi.kpi_name,
            'uom': kpi.uom,
            'goodness_indicator': kpi.goodness_indicator,
            'baseline': kpi.baseline,
            'commitment': kpi.commitment,
            'actual': val.actual,
            'remarks': val.remarks,
            'achievement': achievement,
        })
        
    ws_data = {
        'id': ws.id,
        'name': ws.name,
        'leader': ws.leader,
        'inception_date': ws.inception_date,
        'kpis': kpis_data,
    }
    
    toast_html = f'<div id="toast-container" hx-swap-oob="true"><div class="toast toast-success">Saved Workstation "{ws.name}"</div></div>'
    context = {
        'ws': ws_data,
        'dept': dept,
        'month': month,
        'year': year,
    }
    
    response = render(request, 'partials/_ws_card.html', context)
    response.content = response.content + toast_html.encode('utf-8')
    return response
