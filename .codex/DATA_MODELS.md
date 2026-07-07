# DATA_MODELS.md — AMM Complete Model Field Reference

Quick-reference for every model in the project. Use this to avoid guessing field names.

---

## `users` app

### `User` (AUTH_USER_MODEL)
```
id                              UUIDField (PK)
email                           EmailField (unique)
first_name                      CharField(75)
last_name                       CharField(75)
codename                        CharField(20, unique) — B-n / S-n / W-n, set at registration
role                            CharField — male/female/wali/matchmaker/superadmin
gender                          CharField — male/female (null for wali/admin)
profile_picture                 ImageField → media/users/profile_pictures/
subscription_plan               CharField — free/monthly/annual (default: free)
subscription_start              DateTimeField (null)
subscription_end                DateTimeField (null)
provider                        CharField — self/google/apple
provider_id                     CharField (null)
is_active                       BooleanField (default: True)
deactivated_by_user             BooleanField (default: False)
is_private_matchmaking_client   BooleanField (default: False)
last_active                     DateTimeField (null) — updated by middleware
device_token                    CharField (null) — FCM/APNs placeholder
created_at / updated_at
```

### `UserSettings`
```
user                            OneToOneField → User
notification_enabled            BooleanField (default: True)
created_at / updated_at
```

---

## `questions` app

### `MaleBasicInfo`
```
user                            OneToOneField → User
# Step 1
how_found                       JSONField(list) — HOW_FOUND_CHOICES keys
phone                           CharField(30)
date_of_birth                   DateField
city / country                  CharField(100)
# Step 2
sect                            CharField — sunni/salafi
marital_status                  CharField — never_married/polygyny/khula/divorced/widowed
ethnicity                       JSONField(list) — ETHNICITY_CHOICES keys
nationality                     JSONField(list) — NATIONALITY_CHOICES keys
has_children                    BooleanField
children_count                  CharField — 0/1/2/3/4/5_plus
height                          CharField(30) — full display string
weight                          CharField(30) — full display string
pray_5x                         CharField — yes/mostly/no
open_to_relocate                CharField — yes/no/maybe/later
employment                      CharField(200)
education                       CharField — EDUCATION_CHOICES
income                          CharField — INCOME_CHOICES
frame                           CharField — FRAME_CHOICES
languages_spoken                JSONField(list) — LANGUAGE_CHOICES keys
# Step 3 (preferences)
preferred_dress                 CharField — no_hijab/hijab_pants/hijab_abaya/niqab
pref_age_min / pref_age_max     PositiveSmallIntegerField
pref_marital_status             JSONField(list)
pref_ethnicity                  JSONField(list)
# Step 4
pref_country_of_residence       JSONField(list)
relationship_with_islam         TextField
role_as_spouse                  TextField
about_yourself                  TextField
envision_spouse                 TextField
envision_marriage               TextField
spouse_religious_status_pref    TextField
open_to_relocate_details        TextField
health_concerns                 TextField
other_preferences               TextField
created_at / updated_at
# @property
completion_percentage           int (0-100)
age                             int | None
```

### `FemaleBasicInfo`
Same as MaleBasicInfo plus:
```
dress                           CharField — how she dresses
wali_name / wali_relation / wali_number   CharField
```
Minus: `preferred_dress` (male preference field)

### `WaliProfile` (Wali's own Step 1 info)
```
user                            OneToOneField → User
how_found                       JSONField(list)
gender                          CharField — male/female
relation_to_sister              CharField — father/brother/uncle/grandfather/other
phone                           CharField(30)
created_at / updated_at
```

### `WaliBasicInfo` (Sister's data, submitted by wali)
```
user                            OneToOneField → User (the wali)
sister_first_name / sister_last_name  CharField(75)
date_of_birth                   DateField
city / country                  CharField(100)
about                           TextField
[all same fields as FemaleBasicInfo except wali_name/relation/number]
```

### `UserPhoto`
```
id                              UUIDField (PK)
user                            ForeignKey → User
image                           ImageField → media/users/photos/
is_primary                      BooleanField (default: False)
created_at
```

---

## `matches` app

### `Match`
```
id                              UUIDField (PK)
match_id                        CharField(20) — MT-n
male_user                       ForeignKey → User
other_user                      ForeignKey → User (Female/Wali)
initiated_by                    ForeignKey → User (always male_user)
status                          CharField — pending/declined/accepted/cancelled/
                                             wali_requested/wali_accepted/
                                             in_discussion/married/dropped
cancelled_by / cancelled_at     FK → User / DateTimeField
dropped_by / dropped_at         FK → User / DateTimeField
photo_request_status            CharField — none/requested/approved
photo_requested_by              ForeignKey → User (null)
photos_currently_visible        BooleanField (default: False)
photos_revealed_count           PositiveIntegerField (default: 0)
first_photos_revealed_at        DateTimeField (null)
last_photos_revealed_at         DateTimeField (null)
wali_request_status             CharField — none/requested/accepted/declined
wali_requested_at               DateTimeField (null)
wali_responded_at               DateTimeField (null)
requested_at                    DateTimeField (auto_now_add)
responded_at                    DateTimeField (null)
accepted_at                     DateTimeField (null)
in_discussion_at                DateTimeField (null)
married_at                      DateTimeField (null)
last_status_changed_by_admin    ForeignKey → User (null)
created_at / updated_at
unique_together: (male_user, other_user)
```

---

## `wishlists` app

### `SavedProfile`
```
id / user / saved_user          UUID / FK / FK
created_at
unique_together: (user, saved_user)
```

### `ProfileView`
```
id / viewer / viewed_user       UUID / FK / FK
viewed_at                       DateTimeField (auto_now_add)
```

### `BlockedProfile`
```
id / blocker / blocked          UUID / FK / FK
created_at
unique_together: (blocker, blocked)
```

### `HiddenProfile`
```
id / user / hidden_user         UUID / FK / FK
created_at
unique_together: (user, hidden_user)
```

### `Report`
```
id                              UUID
reporter / reported_user        FK / FK
reason                          CharField — fake_profile/inappropriate/spam/harassment/other
details                         TextField (null)
status                          CharField — pending/reviewed/resolved
reviewed_by                     FK → User (null)
reviewed_at                     DateTimeField (null)
admin_notes                     TextField (null)
created_at
```

---

## `notifications` app

### `Notification`
```
id                              UUIDField (PK)
user                            ForeignKey → User
notification_type               CharField (see NotificationType choices)
title / body                    CharField / TextField
data                            JSONField (arbitrary payload)
priority                        CharField — low/normal/high/urgent
websocket_pushed                BooleanField (admin only)
websocket_success               BooleanField (admin only)
is_read                         BooleanField (default: False)
read_at                         DateTimeField (null)
created_at
```

### NotificationType values
```
welcome / pass_changed / account_blocked / profile_approved
connection_request_received / connection_request_accepted
connection_request_declined / connection_request_cancelled
match_created
photo_request_received / photo_request_approved / photo_request_declined
wali_request_received / wali_request_approved / wali_request_declined
unlock_request_received
new_message
private_matchmaking_requested / private_matchmaking_confirmed
pm_approved / pm_declined / pm_match_update / special_match_received
new_user_joined
```

---

## `chat` app

### `ChatRoom`
```
id                              UUIDField (PK)
user                            OneToOneField → User (the normal user)
created_at / updated_at
```

### `Message`
```
id                              UUIDField (PK)
room                            ForeignKey → ChatRoom
sender                          ForeignKey → User (null on SET_NULL)
sender_is_admin                 BooleanField
text                            TextField (null)
attachment                      FileField → media/chat/attachments/<room_id>/<filename>
is_read                         BooleanField (default: False)
read_at                         DateTimeField (null)
created_at
```

---

## `matchmaking` app

### `PrivateMatchmakingRequest`
```
id                              UUIDField (PK)
request_id                      CharField(20) — RQ-n
user                            ForeignKey → User
status                          CharField — pending/approved/declined
admin_notes                     TextField (null)
reviewed_by                     ForeignKey → User (null)
reviewed_at                     DateTimeField (null)
created_at / updated_at
```

---

## `private_matches` app

### `PrivateMatchSuggestion`
```
id                              UUIDField (PK)
private_client                  ForeignKey → User (is_private_matchmaking_client=True)
prospect                        ForeignKey → User
suggested_by                    ForeignKey → User (matchmaker)
status                          CharField — pending_client_review / client_accepted /
                                             client_declined / sent_to_prospect /
                                             prospect_accepted / prospect_declined
client_feedback                 TextField (null)
client_responded_at             DateTimeField (null)
prospect_responded_at           DateTimeField (null)
created_at / updated_at
unique_together: (private_client, prospect)
```
