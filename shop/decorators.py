from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect



def admin_required(view_func):
    """Chỉ Admin (staff/superuser) được truy cập."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Vui lòng đăng nhập để tiếp tục.")
            return redirect("dang_nhap")
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, "Bạn không có quyền truy cập khu vực Admin.")
            return redirect("home")
        return view_func(request, *args, **kwargs)

    return _wrapped
