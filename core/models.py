# -*- coding: utf-8 -*-
import re
from jsonfield import JSONField

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, UserManager
from django.core import validators
from django.core.mail import send_mail
from django.db import models
from django.template.defaultfilters import slugify
from django.utils import timezone
from django.utils.http import urlquote
from django.utils.translation import ugettext_lazy as _


class TimtecUser(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(_('Username'), max_length=30, unique=True,
        help_text=_('Required. 30 characters or fewer. Letters, numbers and '
                    './+/-/_ characters'),
        validators=[
            validators.RegexValidator(re.compile('^[\w.+-]+$'), _('Enter a valid username.'), 'invalid')
        ])

    email = models.EmailField(_('Email address'), blank=False, unique=True)
    first_name = models.CharField(_('First name'), max_length=30, blank=True)
    last_name = models.CharField(_('Last name'), max_length=30, blank=True)
    is_staff = models.BooleanField(_('Staff status'), default=False)
    is_active = models.BooleanField(_('Active'), default=True)
    date_joined = models.DateTimeField(_('Date joined'), default=timezone.now)

    picture = models.ImageField(_("Picture"), upload_to='user-pictures', blank=True)
    occupation = models.CharField(_('Occupation'), max_length=30, blank=True)
    city = models.CharField(_('City'), max_length=30, blank=True)
    site = models.URLField(_('Site'), blank=True)
    biography = models.TextField(_('Biography'), blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def __unicode__(self):
        if self.first_name or self.last_name:
            return self.get_full_name()
        return self.email

    def get_absolute_url(self):
        return "/users/%s/" % urlquote(self.email)

    def get_picture_url(self):
        location = "/%s/%s" % (settings.MEDIA_URL, self.picture)
        return re.sub('/+', '/', location)

    def get_full_name(self):
        full_name = '%s %s' % (self.first_name, self.last_name)
        return full_name.strip()

    def get_short_name(self):
        return self.first_name

    def email_user(self, subject, message, from_email=None):
        send_mail(subject, message, from_email, [self.email])


class Video(models.Model):
    name = models.CharField(max_length=255)
    youtube_id = models.CharField(max_length=100)

    class Meta:
        verbose_name = _('Video')
        verbose_name_plural = _('Videos')

    def __unicode__(self):
        return self.name


class Course(models.Model):
    STATES = (
        ('new', _('New')),
        ('private', _('Private')),
        ('public', _('Public')),
    )

    slug = models.SlugField(_('Slug'), max_length=255, unique=True)
    name = models.CharField(_('Name'), max_length=255)
    intro_video = models.ForeignKey(Video, verbose_name=_('Intro video'))
    application = models.TextField(_('Application'))
    requirement = models.TextField(_('Requirement'))
    abstract = models.TextField(_('Abstract'))
    structure = models.TextField(_('Structure'))
    workload = models.TextField(_('Workload'))
    pronatec = models.TextField(_('Pronatec'))
    status = models.CharField(_('Status'), choices=STATES, default=STATES[0][0], max_length=128)
    publication = models.DateField(_('Publication'), )
    professors = models.ManyToManyField(TimtecUser, related_name='professorcourse_set', through='CourseProfessor')
    students = models.ManyToManyField(TimtecUser, related_name='studentcourse_set', through='CourseStudent')

    class Meta:
        verbose_name = _('Course')
        verbose_name_plural = _('Courses')

    def __unicode__(self):
        return self.name

    @property
    def unit_set(self):
        return Unit.objects.filter(lesson__in=self.lesson_set.all()).order_by('lesson')

    def first_lesson(self):
        return self.lesson_set.all()[0]

    def enroll_student(self, student):
        params = { 'user': student, 'course': self }
        try:
            return CourseStudent.objects.get(**params)
        except CourseStudent.DoesNotExist:
            return CourseStudent.objects.create(**params)


class CourseStudent(models.Model):
    user = models.ForeignKey(TimtecUser, verbose_name=_('Student'))
    course = models.ForeignKey(Course, verbose_name=_('Course'))

    class Meta:
        unique_together = (('user', 'course'),)

    def percent_progress(self):
        units = self.course.unit_set.count()
        units_done = StudentProgress.objects.exclude(complete=None)\
                                            .filter(user=self.user, unit__lesson__course=self.course)\
                                            .count()
        return int( 100 * float(units_done) / float(units) )


class CourseProfessor(models.Model):
    POSITIONS = (
        ('instructor', _('Instructor')),
        ('assistant', _('Assistant')),
        ('pedagogy_assistant', _('Pedagogy Assistant')),
    )

    user = models.ForeignKey(TimtecUser, verbose_name=_('Professor'))
    course = models.ForeignKey(Course, verbose_name=_('Course'))
    biography = models.TextField(_('Biography'))
    job = models.CharField(_('Job'), choices=POSITIONS, default=POSITIONS[0][0], max_length=128)

    class Meta:
        unique_together = (('user', 'course'),)
        verbose_name = _('Course Professor')
        verbose_name_plural = _('Course Professors')

    def __unicode__(self):
        return u'%s @ %s' % (self.user, self.course)


class Lesson(models.Model):
    slug = models.SlugField(_('Slug'), max_length=255, editable=False, unique=True)
    name = models.CharField(_('Name'), max_length=255)
    desc = models.CharField(_('Description'), max_length=255)
    position = models.PositiveIntegerField(_('Position'))
    course = models.ForeignKey(Course, verbose_name=_('Course'))

    class Meta:
        verbose_name = _('Lesson')
        verbose_name_plural = _('Lessons')
        ordering = ['position']

    def save(self, **kwargs):
        if not self.id and self.name:
            self.slug = slugify(self.name)
        super(Lesson, self).save(**kwargs)

    def __unicode__(self):
        return self.name

    def activity_count(self):
        return self.unit_set.exclude(activity=None).count()

    def unit_count(self):
        return self.unit_set.all().count()

    def video_count(self):
        return self.unit_set.exclude(video=None).count()


class Activity(models.Model):
    """
    Generic class to activities
    Data templates (data e type atributes):
    Multiple choice
        type: multiplechoice
        data: {question: "", choices: ["choice1", "choice2", ...]}
        expected_answer_data: {choices: [0, 2, 5]} # list of espected choices, zero starting
    Single choice
        type: singlechoice
        data: {question: "", choices: ["choice1", "choice2", ...]}
        expected_answer_data: {choice: 1}
    """
    type = models.CharField(_('Type'), max_length=255)
    data = JSONField(_('Data'))
    expected_answer = JSONField(_('Expected answer'))

    class Meta:
        verbose_name = _('Activity')
        verbose_name_plural = _('Activities')

    def __unicode__(self):
        return u'%s dt %s a %s' % (self.type, self.data, self.expected_answer)


class Unit(models.Model):
    lesson = models.ForeignKey(Lesson, verbose_name=_('Lesson'))
    video = models.ForeignKey(Video, verbose_name=_('Video'), null=True, blank=True)
    activity = models.ForeignKey(Activity, verbose_name=_('Activity'), null=True, blank=True)
    position = models.PositiveIntegerField(_('Position'))

    class Meta:
        verbose_name = _('Unit')
        verbose_name_plural = _('Units')
        ordering = ['position']

    def __unicode__(self):
        return u'%s) %s - %s - %s' % (self.position, self.lesson, self.video, self.activity)


class Answer(models.Model):
    activity = models.ForeignKey(Activity, verbose_name=_('Activity'))
    user = models.ForeignKey(TimtecUser, verbose_name=_('Professor'))
    timestamp = models.DateTimeField(auto_now_add=True, editable=False)
    answer = models.TextField(_('Answer'))

    class Meta:
        verbose_name = _('Answer')
        verbose_name_plural = _('Answers')


class StudentProgress(models.Model):
    user = models.ForeignKey(TimtecUser, verbose_name=_('Student'))
    unit = models.ForeignKey(Unit, verbose_name=_('Unit'))
    complete = models.DateTimeField(editable=False, null=True)
    last_access = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        unique_together = (('user', 'unit'),)
        verbose_name = _('Student Progress')
