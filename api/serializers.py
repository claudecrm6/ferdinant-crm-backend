from rest_framework import serializers
from .models import Group, Course, Student, Payment, Trash, CRMUser, CRMSession


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = '__all__'


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = '__all__'


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = '__all__'


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['owner', 'status']


class TrashSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trash
        fields = '__all__'


class CRMUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CRMUser
        fields = ['id', 'username', 'name', 'phone', 'address', 'avatar', 'created_at']