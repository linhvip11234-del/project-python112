from rest_framework import serializers

from .models import DonHang, ProductImage, ProductReview, SanPham


class ProductImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ["id", "caption", "sort_order", "image_url"]

    def get_image_url(self, obj):
        request = self.context.get("request")
        if not obj.image:
            return ""
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url


class ProductReviewSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source="user.username", read_only=True)
    stars = serializers.CharField(read_only=True)

    class Meta:
        model = ProductReview
        fields = ["id", "user", "rating", "stars", "title", "comment", "created_at"]
        read_only_fields = ["id", "user", "stars", "created_at"]


class ProductListSerializer(serializers.ModelSerializer):
    current_price = serializers.IntegerField(source="gia_hien_tai", read_only=True)
    average_rating = serializers.FloatField(source="average_rating_value", read_only=True)
    review_count = serializers.IntegerField(source="review_count_value", read_only=True)
    main_image_url = serializers.SerializerMethodField()

    class Meta:
        model = SanPham
        fields = [
            "id",
            "ten",
            "gia",
            "gia_khuyen_mai",
            "flash_sale_price",
            "current_price",
            "ton_kho",
            "trang_thai",
            "average_rating",
            "review_count",
            "main_image_url",
            "mo_ta_ngan",
        ]

    def get_main_image_url(self, obj):
        request = self.context.get("request")
        if not obj.anh:
            return ""
        url = obj.anh.url
        return request.build_absolute_uri(url) if request else url


class ProductDetailSerializer(ProductListSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    reviews = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + [
            "mo_ta",
            "search_tags",
            "images",
            "reviews",
        ]

    def get_reviews(self, obj):
        qs = obj.reviews.filter(is_visible=True).select_related("user")[:10]
        return ProductReviewSerializer(qs, many=True).data


class OrderSerializer(serializers.ModelSerializer):
    san_pham = serializers.CharField(source="san_pham.ten", read_only=True)
    user = serializers.CharField(source="nguoi_dat.username", read_only=True)

    class Meta:
        model = DonHang
        fields = [
            "id",
            "user",
            "san_pham",
            "so_luong",
            "tong_tien_goc",
            "discount_amount",
            "tong_tien",
            "trang_thai",
            "phuong_thuc_tt",
            "voucher_code",
            "tao_luc",
        ]


class CreateReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductReview
        fields = ["rating", "title", "comment"]

    def validate_rating(self, value):
        value = int(value or 0)
        if value < 1 or value > 5:
            raise serializers.ValidationError("rating phải từ 1 đến 5")
        return value

    def validate(self, attrs):
        if not (attrs.get("title") or "").strip() and not (attrs.get("comment") or "").strip():
            raise serializers.ValidationError("Cần nhập title hoặc comment")
        attrs["title"] = (attrs.get("title") or "").strip()
        attrs["comment"] = (attrs.get("comment") or "").strip()
        return attrs
