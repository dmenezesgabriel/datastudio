"""User aggregate: our local account for a caller, linked to an external identity."""


class User:
    """A user account owned by this system.

    ``subject`` is the external IdP identifier (the OIDC ``sub`` claim) this
    account is linked to; it is ``None`` for the guest — a user we mint locally
    without any external sign-in. When a real IdP (MSAL/OIDC) is wired, accounts
    are looked up / upserted by ``subject`` on first sign-in.

    Example:
        alice = User.for_subject("u-42", "Alice", subject="entra|abc123", email="alice@corp.com")
        guest = User.guest("guest", "Guest")
    """

    def __init__(
        self, user_id: str, display_name: str, subject: str | None, email: str | None
    ) -> None:
        """Build a user from its local id, display name, and optional external subject/email."""
        self.user_id = user_id
        self.display_name = display_name
        self.subject = subject
        self.email = email

    @classmethod
    def guest(cls, user_id: str, display_name: str) -> "User":
        """Mint a local-only guest account (no external identity, so no email)."""
        return cls(user_id, display_name, subject=None, email=None)

    @classmethod
    def for_subject(
        cls, user_id: str, display_name: str, subject: str, email: str | None
    ) -> "User":
        """Build an account linked to an external IdP subject (the OIDC ``sub``) and its email."""
        return cls(user_id, display_name, subject, email)

    @property
    def is_guest(self) -> bool:
        """True when this account has no external identity (an unauthenticated caller)."""
        return self.subject is None
