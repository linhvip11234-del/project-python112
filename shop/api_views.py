from django.db import models
from django.db.models import Avg, Count
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DonHang, ProductReview, SanPham
from .serializers import CreateReviewSerializer, OrderSerializer, ProductDetailSerializer, ProductListSerializer, ProductReviewSerializer


class ApiHealthView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({"status": "ok", "service": "shop-api"})


class ProductListApiView(generics.ListAPIView):
    serializer_class = ProductListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = SanPham.objects.filter(trang_thai="active").annotate(
            average_rating_value=Avg("reviews__rating", filter=models.Q(reviews__is_visible=True)),
            review_count_value=Count("reviews", filter=models.Q(reviews__is_visible=True), distinct=True),
        )
        q = (self.request.GET.get("q") or "").strip()
        min_price = self.request.GET.get("min_price")
        max_price = self.request.GET.get("max_price")
        if q:
            qs = qs.filter(
                models.Q(ten__icontains=q)
                | models.Q(mo_ta__icontains=q)
                | models.Q(search_tags__icontains=q)
            )
        products = list(qs.order_by("-id"))
        if min_price:
            try:
                products = [p for p in products if int(p.gia_hien_tai or 0) >= int(min_price)]
            except Exception:
                pass
        if max_price:
            try:
                products = [p for p in products if int(p.gia_hien_tai or 0) <= int(max_price)]
            except Exception:
                pass
        return products


class ProductDetailApiView(generics.RetrieveAPIView):
    serializer_class = ProductDetailSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return SanPham.objects.annotate(
            average_rating_value=Avg("reviews__rating", filter=models.Q(reviews__is_visible=True)),
            review_count_value=Count("reviews", filter=models.Q(reviews__is_visible=True), distinct=True),
        ).prefetch_related("images", "reviews__user")


class OrderListApiView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = DonHang.objects.select_related("san_pham", "nguoi_dat")
        if not self.request.user.is_staff:
            qs = qs.filter(nguoi_dat=self.request.user)
        return qs.order_by("-id")


class ProductReviewListApiView(generics.ListAPIView):
    serializer_class = ProductReviewSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return ProductReview.objects.filter(is_visible=True, san_pham_id=self.kwargs["pk"]).select_related("user")


class ProductReviewCreateApiView(generics.CreateAPIView):
    serializer_class = CreateReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        product = generics.get_object_or_404(SanPham, pk=self.kwargs["pk"])
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review, _ = ProductReview.objects.update_or_create(
            san_pham=product,
            user=request.user,
            defaults={**serializer.validated_data, "is_visible": True},
        )
        return Response(ProductReviewSerializer(review).data, status=201)
