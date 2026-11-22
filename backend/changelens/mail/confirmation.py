"""The early-bird list's confirmation mail (double opt-in), in English and German. Plain text.

WORDING PENDING LEGAL REVIEW (L4, L23 in tasks/launch-todo.md): every sentence below is a draft. The
imprint line is a placeholder; the sender's imprint details must replace it before the first mail is
sent. The mail says why it was sent, carries the confirmation link and says what happens when it is
ignored. It has no marketing content, no price and no discount figure, and must not gain any: a
confirmation mail that advertises is itself unsolicited advertising.
"""
from __future__ import annotations

LOCALES = ("en", "de")

# Draft wording, pending legal review. `{link}` and `{days}` are the only variables.
_MAILS = {
    "en": ("Confirm your address for the ChangeLens early-bird list",
           "You are receiving this email because this address was entered in the early-bird list form on "
           "the ChangeLens website.\n"
           "\n"
           "To confirm your address, open this link:\n"
           "{link}\n"
           "\n"
           "If you did not ask for this, ignore this email. An address that is not confirmed is deleted "
           "after {days} days, and nothing is stored after that.\n"
           "\n"
           "[Placeholder: the sender's imprint details go here before the first mail is sent.]\n"),
    "de": ("Bestätige deine Adresse für die Early-Bird-Liste von ChangeLens",
           "Du erhältst diese E-Mail, weil diese Adresse im Formular für die Early-Bird-Liste auf der "
           "ChangeLens-Website eingetragen wurde.\n"
           "\n"
           "Um deine Adresse zu bestätigen, öffne diesen Link:\n"
           "{link}\n"
           "\n"
           "Wenn du das nicht warst, ignoriere diese E-Mail. Eine nicht bestätigte Adresse wird nach "
           "{days} Tagen gelöscht; danach ist nichts mehr gespeichert.\n"
           "\n"
           "[Platzhalter: Hier stehen vor dem ersten Versand die Impressumsangaben des Absenders.]\n"),
}


def confirmation_mail(locale: str, link: str, pending_days: int) -> tuple[str, str]:
    """(subject, body) for a sign-up in `locale`. The address itself is never part of the text."""
    subject, body = _MAILS[locale]
    return subject, body.format(link=link, days=pending_days)
