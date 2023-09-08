from django.db import models, transaction
from django.core.exceptions import ObjectDoesNotExist
from .validators import validate_percentage
from django.utils.translation import gettext_lazy as _
import recurrence.fields
from .exceptions import *
from django.utils.timezone import make_aware
from django.utils import timezone
import math
from recurrence.fields import RecurrenceField
from django.db.models import Q
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from datetime import datetime, time

from django.core.exceptions import ValidationError
from .constants import *


class CustomAccountManager(BaseUserManager):
    def create_user(self, email, password, **other_fields):

        if not email:
            raise ValueError(_('You must provide an email.'))

        email = self.normalize_email(email)
        user = self.model(email=email, **other_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, **other_fields):
        other_fields.setdefault('is_staff', True)
        other_fields.setdefault('is_superuser', True)

        if other_fields.get('is_staff') is not True:
            raise ValueError('Superuser must be assigned to is_staff = True.')
        if other_fields.get('is_superuser') is not True:
            raise ValueError(
                'Superuser must be assigned to is_superuser = True.')

        return self.create_user(email, password, **other_fields)


class Member(AbstractBaseUser, PermissionsMixin):
    TEAM_A = 'A'
    TEAM_B = 'B'
    TEAM_C = 'C'
    NO_TEAM = 'No-Team'
    TEAM_CHOICES = [
        (TEAM_A, 'A-Team'),
        (TEAM_B, 'B-Team'),
        (TEAM_C, 'C-Team'),
        (NO_TEAM, 'No-Team')
    ]
    GENDER_MALE = 'M'
    GENDER_FEMALE = 'F'
    GENDER_CHOICES = [
        (GENDER_MALE, 'Male'),
        (GENDER_FEMALE, 'Female'),
    ]

    email = models.EmailField(_('e-mail'), unique=True)
    member_n = models.CharField(_('member #'), max_length=10, blank=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    level = models.IntegerField(
        validators=[validate_percentage], null=True, default=50)
    start_date = models.DateTimeField(default=timezone.now)
    gender = models.CharField(max_length=7, choices=GENDER_CHOICES)
    team = models.CharField(max_length=7, choices=TEAM_CHOICES, blank=True)
    profile_pic = models.ImageField(
        default='profile_pics/default.jpeg', upload_to='profile_pics')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_pro = models.BooleanField(default=False)
    color = models.CharField(max_length=7, default='#ff0000')
    is_superuser = models.BooleanField(default=False)
    objects = CustomAccountManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'gender']

    @staticmethod
    def get_available_pros(datetime_start, datetime_end):
        # Find the dates that overlap with the specified time range
        overlapping_dates = Date.objects.filter(
            datetime_start__lt=datetime_end,
            datetime_end__gt=datetime_start
        )

        # Extract the pros assigned to overlapping dates
        busy_pros = overlapping_dates.values_list(
            'assigned_pros', flat=True)

        # Find the Pros (Members) who do not have overlapping assignments
        available_pros = Member.objects.filter(
            is_pro=True
        ).exclude(
            id__in=busy_pros
        ).distinct()

        return available_pros

    def __str__(self):
        if self.first_name and self.last_name:
            return self.first_name + ' ' + self.last_name[0] + '.'
        else:
            return str(self.email)

    def get_fut_participations_registered(self):
        # Returns a query set with the future participations registered for
        return Participation.objects.filter(member=self, date__datetime_start__gte=timezone.now()).order_by('date__datetime_start')

    def get_fut_activities_registered(self):
        # Return a query with all the Activities the Member is registered for in the future.
        return Activity.objects.filter(date__participation__member=self, date__datetime_start__gte=timezone.now()).distinct()

    def get_fut_events_registered(self):
        # Returns a query set with the future Events the Member is registered for.
        return Event.objects.filter(activity__date__participation__member=self, activity__date__datetime_start__gte=timezone.now()).distinct()

    def get_next_activity(self):
        try:
            return self.get_fut_activities_registered().order_by('date__datetime_start')[0]
        except:
            return None

    def get_available_activities(self):
        excl_gen = 'F' if self.gender == 'M' else 'M'
        return Activity.objects.filter(type='clinic', date__datetime_start__gte=timezone.now()).exclude(event__gender=excl_gen).distinct()

    def get_level(self):
        if self.level:
            return self.level
        else:
            return 0


class Venue(models.Model):
    name = models.CharField("Venue Name", max_length=120)
    address = models.CharField(max_length=300)
    zip_code = models.CharField("Zip Code", max_length=10)
    phone = models.CharField("Contact Phone", max_length=30)
    web = models.URLField("Website Address")
    email = models.EmailField("Email Address")

    def __str__(self):
        return self.name


class Event(models.Model):
    EVENT_MALE = 'M'
    EVENT_FEMALE = 'F'
    EVENT_MIXED = 'MIXED'

    PART_GENDER_CHOICES = [
        (EVENT_MALE, 'Male'),
        (EVENT_FEMALE, 'Female'),
        (EVENT_MIXED, 'Mixed')]

    TEAM_A = 'A'
    TEAM_B = 'B'
    TEAM_C = 'C'
    NO_TEAM = 'No-Team'

    TEAM_CHOICES = [
        (TEAM_A, 'A-Team'),
        (TEAM_B, 'B-Team'),
        (TEAM_C, 'C-Team'),
        (NO_TEAM, 'No-Team')
    ]

    title = models.CharField('Event Title', max_length=120, blank=False)
    description = models.TextField("Description", blank=True)
    gender = models.CharField("Gender", max_length=7,
                              choices=PART_GENDER_CHOICES)
    team = models.CharField("Team", max_length=12,
                            blank=True, choices=TEAM_CHOICES)

    REQUIRED_FIELDS = ['title', 'gender', 'team']

    def __str__(self):
        return self.title

    def get_activities(self):
        return Activity.objects.filter(event=self)

    def get_fut_dates(self, number=40):
        # Returns a list of the future Dates of the Event's activities
        activities = Activity.objects.filter(event__id=self.id)
        if activities:
            # Retrieves the future dates
            dates = Date.objects.filter(activity__event__id=self.id).filter(
                datetime_start__gte=timezone.now()).order_by('datetime_start')[:number]
            if not dates:
                # If there are no future dates, then it will return the past dates
                dates = Date.objects.filter(
                    activity__event__id=self.id).order_by('-datetime_start')
            return dates[:number]
        return []

    def get_next_date(self):
        """
        Returns the next single date of the Event. If there are none,
        it returns None.
        """
        try:
            return self.get_fut_dates(1)[0]
        except:
            return None


class Court(models.Model):
    # Make sure that the HTML in calendar matches these options
    STADIUM_COURT = 'Stadium Court'
    COURT_1 = 'Court 1'
    COURT_2 = 'Court 2'
    COURT_3 = 'Court 3'
    COURT_4 = 'Court 4'
    COURT_5 = 'Court 5'
    COURT_6 = 'Court 6'
    COURT_7 = 'Court 7'

    COURT_CHOICES = (
        (STADIUM_COURT, 'Stadium Court'),
        (COURT_1, 'Court 1'),
        (COURT_2, 'Court 2'),
        (COURT_3, 'Court 3'),
        (COURT_4, 'Court 4'),
        (COURT_5, 'Court 5'),
        (COURT_6, 'Court 6'),
        (COURT_7, 'Court 7'),
    )

    name = models.CharField(max_length=20, choices=COURT_CHOICES, unique=True)

    @staticmethod
    def get_open_courts(datetime_start, datetime_end):
        # This returns all the courts that are not already reserved at the given time range.

        occupied_courts = Court.objects.filter(
            date__datetime_start__lte=datetime_end,
            date__datetime_end__gte=datetime_start
        )

        available_courts = Court.objects.exclude(id__in=occupied_courts)
        return available_courts

    def __str__(self):
        return self.name


class Activity(models.Model):
    TYPE_PRIVATE = 'private'
    TYPE_COURT = 'court'
    TYPE_CLINIC = 'clinic'
    TYPE_SEMIPRIVATE = 'semiprivate'
    TYPE_CHOICES = (
        (TYPE_PRIVATE, 'Private Lesson'),
        (TYPE_SEMIPRIVATE, 'Semi-Private Lesson'),
        (TYPE_COURT, 'Court Reservation'),
        (TYPE_CLINIC, 'Clinic')
    )
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
    )
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, blank=True, null=True, default=None)
    title = models.CharField('Activity Title', max_length=120, blank=True)
    recurrences = RecurrenceField(blank=True, null=True)
    start_time = models.TimeField("Start Time", blank=True, null=True)
    end_time = models.TimeField("End Time", blank=True, null=True)
    capacity = models.IntegerField("Capacity", default=MAX_P_P_COURT)
    is_active = models.BooleanField("Active", default=True)

    REQUIRED_FIELDS = ['type', 'title', 'recurrences',
                       'start_time', 'end_time', 'capacity', 'is_active']

    def __str__(self):
        return f"{self.get_title()} - {self.get_dates_desc()}"

    def save(self, court=None, *args, **kwargs,):
        with transaction.atomic():
            if court:
                self._create_activity_with_court(court, *args, **kwargs)
            elif self.pk is None:
                self._create_activity(*args, **kwargs)
            else:
                self._update_activity(*args, **kwargs)

    def _create_activity_with_court(self, court, *args, **kwargs):
        with transaction.atomic():
            super(Activity, self).save(*args, **kwargs)
            try:
                self.create_date_with_court(court)
            except DateCreationError as dce:
                self.delete()
                raise ActivityCreationError(
                    f"Error creating the Activity: {dce}.")

    def _create_activity(self, *args, **kwargs):
        with transaction.atomic():
            super(Activity, self).save(*args, **kwargs)
            try:
                self.update_date_instances()
            except DateCreationError as dce:
                self.delete()
                raise ActivityCreationError(
                    f"Error creating the Activity: {dce}.")

    def _update_activity(self):
        with transaction.atomic():
            old_act = Activity.objects.get(pk=self.pk)
            old_occur = self._get_sorted_occurrences(old_act)

            if self._times_changed(old_act):
                self._update_activity_times()
            elif self._dates_or_capacity_changed(old_occur, old_act):
                self._update_activity_dates(old_occur)

    def _get_sorted_occurrences(self, activity):
        return sorted(list(activity.recurrences.occurrences(dtend=DATE_LIMIT)))

    def _times_changed(self, old_activity):
        return (
            str(old_activity.start_time) != str(self.start_time)
            or str(old_activity.end_time) != str(self.end_time)
        )

    def _dates_or_capacity_changed(self, old_occurrences, old_activity):
        return (
            old_occurrences != self._get_sorted_occurrences(self)
            or old_activity.capacity != self.capacity
        )

    def _update_activity_times(self):
        self.delete_future_dates()
        super(Activity, self).save()
        try:
            self.update_date_instances()
        except DateUpdateError as due:
            raise ActivityUpdateError(
                f"Error updating the new Activity's times: {due}.")

    def _update_activity_dates(self, old_occurrences):
        super(Activity, self).save()
        try:
            self.update_date_instances(old_occurrences)
        except DateUpdateError as due:
            raise ActivityUpdateError(
                f"Error updating the new Activity's dates: {due}.")

    def clean(self):
        super().clean()

        errors = {}

        if self.start_time is not None and self.end_time is not None:
            # Check that times are on the hour or half hour
            if self.start_time.minute not in [0, 30]:
                errors['start_time'] = ValidationError(
                    'Start time must be on the hour or half hour')
            if self.end_time.minute not in [0, 30]:
                errors['end_time'] = ValidationError(
                    'End time must be on the hour or half hour')

            # Check that times are between 6AM and 10PM
            if not time(6, 0) <= self.start_time <= time(22, 0):
                errors['start_time'] = ValidationError(
                    'Start time must be between 6:00 AM and 10:00 PM')
            if not time(6, 0) <= self.end_time <= time(22, 0):
                errors['end_time'] = ValidationError(
                    'End time must be between 6:00 AM and 10:00 PM')

            if self.start_time and self.end_time and self.start_time >= self.end_time:
                errors['start_time'] = ValidationError(
                    "End time must be after start time.")
                errors['end_time'] = ValidationError(
                    "End time must be after start time.")
        if self.capacity < 1:
            errors['capacity'] = ValidationError(
                f'The capacity must be greater than 0')

        if self.type == Activity.TYPE_CLINIC and not self.event:
            errors['type'] = ValidationError(
                f'A {self.get_type_display()} must be linked to an Event')

        if self.type == Activity.TYPE_PRIVATE:
            if not 1 <= self.capacity <= MAX_P_P_COURT:
                errors['capacity'] = ValidationError(
                    f'A private lesson must have a capacity between 1 and {MAX_P_P_COURT}')

        if self.type != Activity.TYPE_CLINIC and self.event is not None:
            errors['type'] = ValidationError(
                f'A {self.get_type_display()} cannot be linked to an Event')

        if errors:
            raise ValidationError(errors)

    def get_next_date(self):
        next_date = Date.objects.filter(
            activity__id=self.id, datetime_start__gte=timezone.now()).order_by('datetime_start').first()
        if next_date:
            return next_date
        else:
            return Date.objects.filter(activity__id=self.id).order_by('-datetime_start').first()

    def get_formatted_datetime(self, date, hour, minute):
        return make_aware(date.replace(hour=hour, minute=minute, second=0, microsecond=0))

    def get_rules(self):
        formatted_rules = []

        for rule in self.recurrences.rrules:
            formatted_rules.append(rule.to_text())

        rules_as_string = "\n".join(formatted_rules)

        return rules_as_string

    def is_clinic(self):
        return self.type == Activity.TYPE_CLINIC

    def get_title(self):
        try:
            return self.event.title
        except:
            return str(f"{self.title}")

    def get_all_dates(self):
        return Date.objects.filter(activity__id=self.id).order_by('datetime_start')

    def get_fut_dates(self, number=MAX_DATES):
        # Returns a query list with the "number" amount of future Date instances of the activity
        fut_dates = Date.objects.filter(
            activity__id=self.id, datetime_start__gte=timezone.now()).order_by('datetime_start')[:number]

        if not fut_dates:
            # Handle the case where no future dates are found
            return None

        return fut_dates

    def delete_future_dates(self):
        """
        Deletes all future dates associated with this activity.
        """
        future_dates = Date.objects.filter(
            activity=self, datetime_start__gte=timezone.now())
        future_dates.delete()

    def get_host(self):
        if self.get_next_date():
            host = Participation.objects.filter(
                date__id=self.get_next_date().id).order_by('date_registered').first()
            if host:
                return host.member
        return None

    def get_dates_desc(self):
        # Returns a string with the description of the fut or past dates of the activity
        # if all dates are in the past.
        try:
            return str("On " + self.get_next_date().print_start_date())
        except:
            return "No more future dates"

    def get_date_by_datetime(self, datetime_start):
        # Returns the date instance based on the datetime_start
        try:
            date = Date.objects.get(
                activity_id=self.id, datetime_start=datetime_start)
            return date
        except:
            return None

    def print_next_date(self):
        # Returns the future Date formatted date
        try:
            return self.get_next_date().print_date()
        except:
            return "No next date"

    def get_participants(self):
        try:
            return self.get_next_date().get_all_parts()
        except:
            return "No participants for no date"

    def create_date_with_court(self, court) -> None:
        try:
            date = self.recurrences.occurrences()[0]
            datetime_start = self.get_formatted_datetime(
                date, self.start_time.hour, self.start_time.minute)
            datetime_end = self.get_formatted_datetime(
                date, self.end_time.hour, self.end_time.minute)
            date = Date(activity=self, datetime_start=datetime_start,
                        datetime_end=datetime_end, capacity=self.capacity)
            date.save(court)
        except:
            raise DateCreationError(
                "Could not assign the Court instance to the Date created")

    def update_date_instances(self, old_occurrences=None, limit=MAX_DATES) -> None:
        """
        Creates/deletes dates and adjusts courts based on the recurrence field and capacity. 
        It accepts a list with the old occurrences in order to compare
        if there are dates that should be deleted or adjusted. It only deletes or adjusts future
        dates.
        """
        # It needs to be an unaware date, otherwise, it creates errors with recurrences.
        today = datetime.today()

        to_create = list(self.recurrences.between(
            today, DATE_LIMIT))[:limit]
        # Checks if old_occurrences has been passed as an argument.
        if old_occurrences:
            # Based on the sets, to_create only has the dates that have been added.
            to_create = sorted(
                list(set(to_create) - set(old_occurrences)))[:limit]
            # Based on the sets, to_delete only has the dates that have been removed.
            to_delete = sorted(list(set(old_occurrences) -
                                    set(self.recurrences.between(today, DATE_LIMIT_DELETION))))
            for date in to_delete:
                datetime_start = self.get_formatted_datetime(
                    date, self.start_time.hour, self.start_time.minute)
                date = self.get_date_by_datetime(datetime_start)
                if date:
                    date.delete()

            # For updating the dates' capacity and courts
            for old_date in old_occurrences:
                datetime_start = self.get_formatted_datetime(
                    old_date, self.start_time.hour, self.start_time.minute)
                date = self.get_date_by_datetime(datetime_start)
                if date:
                    if self.capacity != date.capacity:
                        date.capacity = self.capacity
                        try:
                            date.save()
                        except ValueError as ve:
                            raise ValueError(
                                f"Error updating the courts: {ve}.")

        # For creating brand new dates
        for date in to_create:
            datetime_start = self.get_formatted_datetime(
                date, self.start_time.hour, self.start_time.minute)
            datetime_end = self.get_formatted_datetime(
                date, self.end_time.hour, self.end_time.minute)
            Date.objects.create(activity=self, datetime_start=datetime_start,
                                datetime_end=datetime_end, capacity=self.capacity)


class Date(models.Model):
    activity = models.ForeignKey(
        Activity, on_delete=models.CASCADE)
    datetime_start = models.DateTimeField(
        blank=False, null=False, validators=[])
    datetime_end = models.DateTimeField(blank=False, null=False)
    participants = models.ManyToManyField(
        Member, through='Participation', blank=True)
    capacity = models.IntegerField("Capacity", default=MAX_P_P_COURT)
    court = models.ManyToManyField(Court)
    assigned_pros = models.ManyToManyField(
        Member,
        related_name='assigned_dates',
        blank=True,
    )

    REQUIRED_FIELDS = ['activity', 'datetime_start',
                       'datetime_end', 'capacity', 'court']

    def save(self, court=None, *args, **kwargs):
        with transaction.atomic():
            if court:
                super(Date, self).save(*args, **kwargs)
                court = Court.objects.get(name=court)
                self.court.add(court)
            elif self.pk is None:
                num_courts_needed = math.ceil(self.capacity / MAX_P_P_COURT)
                super(Date, self).save(*args, **kwargs)
                courts = Date.get_open_courts(datetime_start=self.datetime_start,
                                              datetime_end=self.datetime_end,
                                              num_courts_needed=num_courts_needed)
                if courts:
                    self.court.add(*courts)
                else:
                    raise DateCreationError(
                        f"Could not create Date for the capacity specified {self.capacity}")
            else:
                try:
                    self.update_courts()
                    super(Date, self).save(*args, **kwargs)
                except ValueError as ve:
                    raise DateUpdateError(
                        f"Could not update the Date {str(self)}: {ve}.")
            return self

    def add_pro(self, pro):
        if pro.is_pro:
            self.assigned_pros.add(pro)
        else:
            # Raise an exception or handle the case where a non-pro is being added
            raise ValueError(
                "Only Pro members can be assigned as pros to a date.")

    def remove_pro(self, pro):
        self.assigned_pros.remove(pro)

    @staticmethod
    def get_open_courts(datetime_start, datetime_end, num_courts_needed):
        open_courts = Court.get_open_courts(datetime_start, datetime_end)
        if len(open_courts) < num_courts_needed:
            return None
        else:
            return list(open_courts)[:num_courts_needed]

    def clean(self):
        super().clean()

        errors = {}

        # Get the time from the datetime fields
        start_time = self.datetime_start.time()
        end_time = self.datetime_end.time()

        # Check that times are on the hour or half hour
        if start_time.minute not in [0, 30]:
            errors['datetime_start'] = ValidationError(
                'Start time must be on the hour or half hour')
        if end_time.minute not in [0, 30]:
            errors['datetime_end'] = ValidationError(
                'End time must be on the hour or half hour')

        # Check that times are between 6AM and 10PM
        if not time(6, 0) <= start_time <= time(22, 0):
            errors['datetime_start'] = ValidationError(
                'Start time must be between 6:00 AM and 10:00 PM')
        if not time(6, 0) <= end_time <= time(22, 0):
            errors['datetime_end'] = ValidationError(
                'End time must be between 6:00 AM and 10:00 PM')

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return str(self.print_date() + ' for ' + self.activity.get_title())

    def __hash__(self):
        return hash((self.datetime_start,))

    def update_courts(self):
        open_courts = Court.get_open_courts(
            self.datetime_start, self.datetime_end)
        courts_used = self.court.all()
        new_courts_needed = (self.capacity - 1) // MAX_P_P_COURT + 1
        if courts_used.exists():
            old_courts_needed = len(courts_used)
        else:
            old_courts_needed = 0

        if new_courts_needed > old_courts_needed:
            courts_needed = new_courts_needed - old_courts_needed
            if len(open_courts) < courts_needed:
                raise ValueError(
                    f"Could not find {courts_needed} open courts")
            else:
                for court in open_courts[:courts_needed]:
                    self.court.add(court)
        elif new_courts_needed < old_courts_needed:
            courts_to_remove = old_courts_needed - new_courts_needed
            for court in list(self.court.all().order_by('-id'))[:courts_to_remove]:
                self.court.remove(court)

    def print_date(self):
        return self.get_datetime_start().strftime('%A, %b %-d - %I:%M%p')

    def print_remaining_days(self):
        date = self.datetime_start.date()
        today = timezone.now().date()

        # Calculate the difference in days
        time_difference = date - today
        remaining_days = time_difference.days

        if remaining_days < 0:
            if remaining_days == -1:
                remaining_days = "Yesterday"
            else:
                remaining_days = str(abs(remaining_days)) + " days ago"
        elif remaining_days == 0:
            remaining_days = 'Today'
        elif remaining_days == 1:
            remaining_days = 'Tomorrow'
        else:
            remaining_days = str(remaining_days) + " days"
        return remaining_days

    def is_registrable(self):
        time_until = self.datetime_start - timezone.now()
        if time_until < timezone.timedelta(hours=24):
            return False
        else:
            return True

    def get_duration(self):
        duration = self.datetime_end - self.datetime_start
        return duration

    def get_formatted_duration(self):
        duration = self.get_duration()
        days = duration.days
        hours, remainder = divmod(duration.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        formatted_duration = ""
        if days > 0:
            formatted_duration += f"{days} day{'s' if days > 1 else ''} "
        if hours > 0:
            formatted_duration += f"{hours} hour{'s' if hours > 1 else ''} "
        if minutes > 0:
            formatted_duration += f"{minutes} minute{'s' if minutes > 1 else ''} "
        if seconds > 0:
            formatted_duration += f"{seconds} second{'s' if seconds > 1 else ''}"

        return formatted_duration.strip()

    def get_activity(self):
        return Activity.objects.get(id=self.id)

    def get_courts(self):
        return self.court.all()

    def print_courts(self):
        courts = self.get_courts()
        if courts:
            courts_names = [court.name for court in courts]
            return ', '.join(courts_names)

    def get_all_parts(self):
        # Returns a list with all the participants with the ones that first registered first
        return [(i.member) for i in Participation.objects.filter(date__id=self.id).order_by('date_registered')]

    def get_parts_on_court(self):
        all_parts = self.get_all_parts()
        on_court = all_parts[:self.capacity]
        # Order the participants by their level
        on_court.sort(key=lambda participant: participant.level, reverse=True)
        return on_court

    def get_parts_on_wait(self):
        all_parts = self.get_all_parts()
        on_wait = all_parts[self.capacity:]
        return on_wait

    def get_datetime_start(self):
        return timezone.localtime(self.datetime_start)

    def get_event_name(self):
        try:
            return Event.objects.get(activity__date__id=self.id).title
        except:
            return "No event yet"

    def print_start_date(self):
        return self.get_datetime_start().strftime(('%A, %b %-d - %I:%M%p'))

    def get_activity(self):
        try:
            return Activity.objects.get(date__id=self.id)
        except:
            return ObjectDoesNotExist

    def get_registered_count(self):
        return Participation.objects.filter(date__id=self.id).count()

    def get_capacity(self):
        return self.capacity

    def get_rem_spots(self):
        return self.get_capacity() - self.get_registered_count()

    def get_cap_pct(self):
        cap_pct = 1 - self.get_rem_spots() / self.get_capacity()
        if cap_pct > 1:
            return 1
        else:
            return '{:.0%}'.format(1 - self.get_rem_spots() / self.get_capacity())

    def print_pros(self):
        pros = self.assigned_pros.all()
        if pros:
            pros_names = [str(pro) for pro in pros]
            pros_string = ', '.join(pros_names)
            return pros_string
        else:
            return "No Pro Assigned"


class Participation(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    date = models.ForeignKey(
        Date, on_delete=models.CASCADE, related_name='participation')
    date_registered = models.DateTimeField(default=timezone.now)
    description = models.TextField(blank=True, max_length=100)

    REQUIRED_FIELDS = ['member', 'date']

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['member', 'date'], name='member_can_sign_in_once'
            )
        ]

    def __str__(self):
        return str(self.member) + " for " + str(self.date)

    def save(self, *args, **kwargs):
        if self.date.get_activity().is_clinic():
            event = Event.objects.get(activity__date__id=self.date.id)
            if event.gender != 'MIXED' and event.gender != self.member.gender:
                raise ValidationError(
                    f"{str(self.member)} can't participate in a event for {event.get_gender_display().lower()}s.")
            else:
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    def get_activity(self):
        try:
            return Activity.objects.get(date=self.date)
        except ObjectDoesNotExist:
            return None

    def get_event(self):
        try:
            return Event.objects.get(activity__date=self.date)
        except:
            return ObjectDoesNotExist

    def get_greater_parent(self):
        """
        Returns either the Event (if the Activity is a 'clinic' type), 
        or the Activity (if the Activity is a 'private' or 'court' type)
        """
        if Activity.objects.get(date=self.date).type == 'clinic':
            return self.get_event()
        else:
            return self.get_activity()
