from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages

def redirect_root(request):
    if request.user.is_authenticated:
        if request.user.is_admin():
            return redirect('plant_dashboard')
        elif request.user.department:
            return redirect('dept_overview', dept_id=request.user.department.id)
        else:
            # User without department and not admin (fallback)
            messages.error(request, "User department is not configured. Contact Administrator.")
            logout(request)
            return redirect('login')
    return redirect('login')

def login_view(request):
    if request.user.is_authenticated:
        return redirect_root(request)

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect_root(request)
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    
    return render(request, 'auth/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('login')
