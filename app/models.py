# ContentDB
# Copyright (C) 2018  rubenwardy
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


import enum, datetime

from app import app, gravatar
from urllib.parse import urlparse

from flask import Flask, url_for
from flask_sqlalchemy import SQLAlchemy, BaseQuery
from flask_migrate import Migrate
from flask_user import login_required, UserManager, UserMixin
from sqlalchemy import func, CheckConstraint
from sqlalchemy_searchable import SearchQueryMixin
from sqlalchemy_utils.types import TSVectorType
from sqlalchemy_searchable import make_searchable


# Initialise database
db = SQLAlchemy(app)
migrate = Migrate(app, db)
make_searchable(db.metadata)


class ArticleQuery(BaseQuery, SearchQueryMixin):
	pass


class UserRank(enum.Enum):
	BANNED         = 0
	NOT_JOINED     = 1
	NEW_MEMBER     = 2
	MEMBER         = 3
	TRUSTED_MEMBER = 4
	EDITOR         = 5
	MODERATOR      = 6
	ADMIN          = 7

	def atLeast(self, min):
		return self.value >= min.value

	def getTitle(self):
		return self.name.replace("_", " ").title()

	def toName(self):
		return self.name.lower()

	def __str__(self):
		return self.name

	@classmethod
	def choices(cls):
		return [(choice, choice.getTitle()) for choice in cls]

	@classmethod
	def coerce(cls, item):
		return item if type(item) == UserRank else UserRank[item]


class Permission(enum.Enum):
	EDIT_PACKAGE       = "EDIT_PACKAGE"
	APPROVE_CHANGES    = "APPROVE_CHANGES"
	DELETE_PACKAGE     = "DELETE_PACKAGE"
	CHANGE_AUTHOR      = "CHANGE_AUTHOR"
	CHANGE_NAME        = "CHANGE_NAME"
	MAKE_RELEASE       = "MAKE_RELEASE"
	DELETE_RELEASE     = "DELETE_RELEASE"
	ADD_SCREENSHOTS    = "ADD_SCREENSHOTS"
	REIMPORT_META      = "REIMPORT_META"
	APPROVE_SCREENSHOT = "APPROVE_SCREENSHOT"
	APPROVE_RELEASE    = "APPROVE_RELEASE"
	APPROVE_NEW        = "APPROVE_NEW"
	EDIT_TAGS          = "EDIT_TAGS"
	CREATE_TAG         = "CREATE_TAG"
	CHANGE_RELEASE_URL = "CHANGE_RELEASE_URL"
	CHANGE_USERNAMES   = "CHANGE_USERNAMES"
	CHANGE_RANK        = "CHANGE_RANK"
	CHANGE_EMAIL       = "CHANGE_EMAIL"
	EDIT_EDITREQUEST   = "EDIT_EDITREQUEST"
	SEE_THREAD         = "SEE_THREAD"
	CREATE_THREAD      = "CREATE_THREAD"
	COMMENT_THREAD     = "COMMENT_THREAD"
	LOCK_THREAD        = "LOCK_THREAD"
	DELETE_REPLY       = "DELETE_REPLY"
	EDIT_REPLY         = "EDIT_REPLY"
	UNAPPROVE_PACKAGE  = "UNAPPROVE_PACKAGE"
	TOPIC_DISCARD      = "TOPIC_DISCARD"
	CREATE_TOKEN       = "CREATE_TOKEN"
	EDIT_MAINTAINERS   = "EDIT_MAINTAINERS"
	CHANGE_PROFILE_URLS = "CHANGE_PROFILE_URLS"

	# Only return true if the permission is valid for *all* contexts
	# See Package.checkPerm for package-specific contexts
	def check(self, user):
		if not user.is_authenticated:
			return False

		if self == Permission.APPROVE_NEW or \
				self == Permission.APPROVE_CHANGES    or \
				self == Permission.APPROVE_RELEASE    or \
				self == Permission.APPROVE_SCREENSHOT or \
				self == Permission.EDIT_TAGS or \
				self == Permission.CREATE_TAG or \
				self == Permission.SEE_THREAD:
			return user.rank.atLeast(UserRank.EDITOR)
		else:
			raise Exception("Non-global permission checked globally. Use Package.checkPerm or User.checkPerm instead.")

	@staticmethod
	def checkPerm(user, perm):
		if type(perm) == str:
			perm = Permission[perm]
		elif type(perm) != Permission:
			raise Exception("Unknown permission given to Permission.check")

		return perm.check(user)

def display_name_default(context):
    return context.get_current_parameters()["username"]

class User(db.Model, UserMixin):
	id           = db.Column(db.Integer, primary_key=True)

	# User authentication information
	username     = db.Column(db.String(50, collation="NOCASE"), nullable=False, unique=True, index=True)
	password     = db.Column(db.String(255), nullable=False, server_default="")
	reset_password_token = db.Column(db.String(100), nullable=False, server_default="")

	rank         = db.Column(db.Enum(UserRank))

	# Account linking
	github_username = db.Column(db.String(50, collation="NOCASE"), nullable=True, unique=True)
	forums_username = db.Column(db.String(50, collation="NOCASE"), nullable=True, unique=True)

	# Access token for webhook setup
	github_access_token = db.Column(db.String(50), nullable=True, server_default=None)

	# User email information
	email         = db.Column(db.String(255), nullable=True, unique=True)
	email_confirmed_at  = db.Column(db.DateTime())

	# User information
	profile_pic   = db.Column(db.String(255), nullable=True, server_default=None)
	active        = db.Column("is_active", db.Boolean, nullable=False, server_default="0")
	display_name  = db.Column(db.String(100), nullable=False, default=display_name_default)

	# Links
	website_url   = db.Column(db.String(255), nullable=True, default=None)
	donate_url    = db.Column(db.String(255), nullable=True, default=None)

	# Content
	notifications = db.relationship("Notification", primaryjoin="User.id==Notification.user_id", \
			order_by="Notification.created_at")

	packages      = db.relationship("Package", backref=db.backref("author", lazy="joined"), lazy="dynamic")
	requests      = db.relationship("EditRequest", backref="author", lazy="dynamic")
	threads       = db.relationship("Thread", backref="author", lazy="dynamic")
	tokens        = db.relationship("APIToken", backref="owner", lazy="dynamic")
	replies       = db.relationship("ThreadReply", backref="author", lazy="dynamic")

	def __init__(self, username=None, active=False, email=None, password=""):
		self.username = username
		self.email_confirmed_at = datetime.datetime.now() - datetime.timedelta(days=6000)
		self.display_name = username
		self.active = active
		self.email = email
		self.password = password
		self.rank = UserRank.NOT_JOINED

	def hasPassword(self):
		return self.password != ""

	def canAccessTodoList(self):
		return Permission.APPROVE_NEW.check(self) or \
				Permission.APPROVE_RELEASE.check(self) or \
				Permission.APPROVE_CHANGES.check(self)

	def isClaimed(self):
		return self.rank.atLeast(UserRank.NEW_MEMBER)

	def getProfilePicURL(self):
		if self.profile_pic:
			return self.profile_pic
		else:
			return gravatar(self.email or "")

	def checkPerm(self, user, perm):
		if not user.is_authenticated:
			return False

		if type(perm) == str:
			perm = Permission[perm]
		elif type(perm) != Permission:
			raise Exception("Unknown permission given to User.checkPerm()")

		# Members can edit their own packages, and editors can edit any packages
		if perm == Permission.CHANGE_AUTHOR:
			return user.rank.atLeast(UserRank.EDITOR)
		elif perm == Permission.CHANGE_RANK or perm == Permission.CHANGE_USERNAMES:
			return user.rank.atLeast(UserRank.MODERATOR)
		elif perm == Permission.CHANGE_EMAIL or perm == Permission.CHANGE_PROFILE_URLS:
			return user == self or user.rank.atLeast(UserRank.ADMIN)
		elif perm == Permission.CREATE_TOKEN:
			if user == self:
				return user.rank.atLeast(UserRank.MEMBER)
			else:
				return user.rank.atLeast(UserRank.MODERATOR) and user.rank.atLeast(self.rank)
		else:
			raise Exception("Permission {} is not related to users".format(perm.name))

	def canCommentRL(self):
		factor = 1
		if self.rank.atLeast(UserRank.ADMIN):
			return True
		elif self.rank.atLeast(UserRank.TRUSTED_MEMBER):
			factor *= 2

		one_min_ago = datetime.datetime.utcnow() - datetime.timedelta(minutes=1)
		if ThreadReply.query.filter_by(author=self) \
				.filter(ThreadReply.created_at > one_min_ago).count() >= 3 * factor:
			return False

		hour_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
		if ThreadReply.query.filter_by(author=self) \
				.filter(ThreadReply.created_at > hour_ago).count() >= 20 * factor:
			return False

		return True

	def canOpenThreadRL(self):
		factor = 1
		if self.rank.atLeast(UserRank.ADMIN):
			return True
		elif self.rank.atLeast(UserRank.TRUSTED_MEMBER):
			factor *= 5

		hour_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
		return Thread.query.filter_by(author=self) \
			.filter(Thread.created_at > hour_ago).count() < 2 * factor

	def __eq__(self, other):
		if other is None:
			return False

		if not self.is_authenticated or not other.is_authenticated:
			return False

		assert self.id > 0
		return self.id == other.id

class UserEmailVerification(db.Model):
	id      = db.Column(db.Integer, primary_key=True)
	user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
	email   = db.Column(db.String(100))
	token   = db.Column(db.String(32))
	user    = db.relationship("User", foreign_keys=[user_id])

class Notification(db.Model):
	id         = db.Column(db.Integer, primary_key=True)

	user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
	user       = db.relationship("User", foreign_keys=[user_id])

	causer_id  = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
	causer     = db.relationship("User", foreign_keys=[causer_id])

	title      = db.Column(db.String(100), nullable=False)
	url        = db.Column(db.String(200), nullable=True)

	package_id = db.Column(db.Integer, db.ForeignKey("package.id"), nullable=True)
	package    = db.relationship("Package", foreign_keys=[package_id])

	created_at = db.Column(db.DateTime, nullable=True, default=datetime.datetime.utcnow)

	def __init__(self, user, causer, title, url, package=None):
		if len(title) > 100:
			title = title[:99] + "…"

		self.user    = user
		self.causer  = causer
		self.title   = title
		self.url     = url
		self.package = package


class License(db.Model):
	id      = db.Column(db.Integer, primary_key=True)
	name    = db.Column(db.String(50), nullable=False, unique=True)
	is_foss = db.Column(db.Boolean,    nullable=False, default=True)

	def __init__(self, v, is_foss=True):
		self.name = v
		self.is_foss = is_foss

	def __str__(self):
		return self.name


class PackageType(enum.Enum):
	MOD  = "Clientmod"
	GAME = "Game"
	TXP  = "Texture Pack"

	def toName(self):
		return self.name.lower()

	def __str__(self):
		return self.name

	@classmethod
	def get(cls, name):
		try:
			return PackageType[name.upper()]
		except KeyError:
			return None

	@classmethod
	def choices(cls):
		return [(choice, choice.value) for choice in cls]

	@classmethod
	def choices_cheat(cls):
		c = cls.choices()
		c.remove((cls.GAME, cls.GAME.value))
		return c

	@classmethod
	def coerce(cls, item):
		return item if type(item) == PackageType else PackageType[item]


class PackageState(enum.Enum):
	WIP = "Work in Progress"
	CHANGES_NEEDED  = "Changes Needed"
	READY_FOR_REVIEW = "Ready for Review"
	APPROVED  = "Approved"
	DELETED = "Deleted"

	def toName(self):
		return self.name.lower()

	def verb(self):
		if self == self.READY_FOR_REVIEW:
			return "Submit for Review"
		elif self == self.APPROVED:
			return "Approve"
		elif self == self.DELETED:
			return "Delete"
		else:
			return self.value

	def __str__(self):
		return self.name

	@classmethod
	def get(cls, name):
		try:
			return PackageState[name.upper()]
		except KeyError:
			return None

	@classmethod
	def choices(cls):
		return [(choice, choice.value) for choice in cls]

	@classmethod
	def coerce(cls, item):
		return item if type(item) == PackageState else PackageState[item]


PACKAGE_STATE_FLOW = {
	PackageState.WIP: set([ PackageState.READY_FOR_REVIEW ]),
	PackageState.CHANGES_NEEDED: set([ PackageState.READY_FOR_REVIEW ]),
	PackageState.READY_FOR_REVIEW: set([ PackageState.WIP, PackageState.CHANGES_NEEDED, PackageState.APPROVED ]),
	PackageState.APPROVED: set([ PackageState.CHANGES_NEEDED ]),
	PackageState.DELETED: set([ PackageState.READY_FOR_REVIEW ]),
}


class PackagePropertyKey(enum.Enum):
	name          = "Name"
	title         = "Title"
	short_desc     = "Short Description"
	desc          = "Description"
	type          = "Type"
	license       = "License"
	media_license = "Media License"
	tags          = "Tags"
	provides      = "Provides"
	repo          = "Repository"
	website       = "Website"
	issueTracker  = "Issue Tracker"
	forums        = "Forum Topic ID"

	def convert(self, value):
		if self == PackagePropertyKey.tags:
			return ",".join([t.title for t in value])
		elif self == PackagePropertyKey.provides:
			return ",".join([t.name for t in value])
		else:
			return str(value)

provides = db.Table("provides",
	db.Column("package_id",    db.Integer, db.ForeignKey("package.id"), primary_key=True),
    db.Column("metapackage_id", db.Integer, db.ForeignKey("meta_package.id"), primary_key=True)
)

Tags = db.Table("tags",
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id"), primary_key=True),
    db.Column("package_id", db.Integer, db.ForeignKey("package.id"), primary_key=True)
)

ContentWarnings = db.Table("content_warnings",
    db.Column("content_warning_id", db.Integer, db.ForeignKey("content_warning.id"), primary_key=True),
    db.Column("package_id", db.Integer, db.ForeignKey("package.id"), primary_key=True)
)

maintainers = db.Table("maintainers",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("package_id", db.Integer, db.ForeignKey("package.id"), primary_key=True)
)

class Dependency(db.Model):
	id              = db.Column(db.Integer, primary_key=True)
	depender_id     = db.Column(db.Integer, db.ForeignKey("package.id"),     nullable=True)
	package_id      = db.Column(db.Integer, db.ForeignKey("package.id"),     nullable=True)
	package         = db.relationship("Package", foreign_keys=[package_id])
	meta_package_id = db.Column(db.Integer, db.ForeignKey("meta_package.id"), nullable=True)
	optional        = db.Column(db.Boolean, nullable=False, default=False)
	__table_args__  = (db.UniqueConstraint("depender_id", "package_id", "meta_package_id", name="_dependency_uc"), )

	def __init__(self, depender=None, package=None, meta=None, optional=False):
		if depender is None:
			return

		self.depender = depender
		self.optional = optional

		packageProvided = package is not None
		metaProvided = meta is not None

		if packageProvided and not metaProvided:
			self.package = package
		elif metaProvided and not packageProvided:
			self.meta_package = meta
		else:
			raise Exception("Either meta or package must be given, but not both!")

	def getName(self):
		if self.meta_package:
			return self.meta_package.name
		elif self.package:
			return self.package.name
		else:
			assert False

	def __str__(self):
		if self.package is not None:
			return self.package.author.username + "/" + self.package.name
		elif self.meta_package is not None:
			return self.meta_package.name
		else:
			raise Exception("Meta and package are both none!")

	@staticmethod
	def SpecToList(depender, spec, cache={}):
		retval = []
		arr = spec.split(",")

		import re
		pattern1 = re.compile("^([a-z0-9_]+)$")
		pattern2 = re.compile("^([A-Za-z0-9_]+)/([a-z0-9_]+)$")

		for x in arr:
			x = x.strip()
			if x == "":
				continue

			if pattern1.match(x):
				meta = MetaPackage.GetOrCreate(x, cache)
				retval.append(Dependency(depender, meta=meta))
			else:
				m = pattern2.match(x)
				username = m.group(1)
				name     = m.group(2)
				user = User.query.filter_by(username=username).first()
				if user is None:
					raise Exception("Unable to find user " + username)

				package = Package.query.filter_by(author=user, name=name).first()
				if package is None:
					raise Exception("Unable to find package " + name + " by " + username)

				retval.append(Dependency(depender, package=package))

		return retval


class Package(db.Model):
	query_class  = ArticleQuery

	id           = db.Column(db.Integer, primary_key=True)

	# Basic details
	author_id    = db.Column(db.Integer, db.ForeignKey("user.id"))
	name         = db.Column(db.Unicode(100), nullable=False)
	title        = db.Column(db.Unicode(100), nullable=False)
	short_desc   = db.Column(db.Unicode(200), nullable=False)
	desc         = db.Column(db.UnicodeText, nullable=True)
	type         = db.Column(db.Enum(PackageType))
	created_at   = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
	approved_at  = db.Column(db.DateTime, nullable=True, default=None)

	name_valid = db.CheckConstraint("name ~* '^[a-z0-9_]+$'")

	search_vector = db.Column(TSVectorType("name", "title", "short_desc", "desc", \
			weights={ "name": "A", "title": "B", "short_desc": "C", "desc": "D" }))

	license_id   = db.Column(db.Integer, db.ForeignKey("license.id"), nullable=False, default=1)
	license      = db.relationship("License", foreign_keys=[license_id])
	media_license_id = db.Column(db.Integer, db.ForeignKey("license.id"), nullable=False, default=1)
	media_license    = db.relationship("License", foreign_keys=[media_license_id])

	state         = db.Column(db.Enum(PackageState), default=PackageState.WIP)

	@property
	def approved(self):
		return self.state == PackageState.APPROVED

	score        = db.Column(db.Float, nullable=False, default=0)
	score_downloads = db.Column(db.Float, nullable=False, default=0)
	downloads     = db.Column(db.Integer, nullable=False, default=0)

	review_thread_id = db.Column(db.Integer, db.ForeignKey("thread.id"), nullable=True, default=None)
	review_thread    = db.relationship("Thread", foreign_keys=[review_thread_id])

	# Downloads
	repo         = db.Column(db.String(200), nullable=True)
	website      = db.Column(db.String(200), nullable=True)
	issueTracker = db.Column(db.String(200), nullable=True)
	forums       = db.Column(db.Integer,     nullable=True)

	provides = db.relationship("MetaPackage", \
			secondary=provides, lazy="select", order_by=db.asc("name"), \
			backref=db.backref("packages", lazy="dynamic", order_by=db.desc("score")))

	dependencies = db.relationship("Dependency", backref="depender", lazy="dynamic", foreign_keys=[Dependency.depender_id])

	tags = db.relationship("Tag", secondary=Tags, lazy="select",
			backref=db.backref("packages", lazy=True))

	content_warnings = db.relationship("ContentWarning", secondary=ContentWarnings, lazy="select",
			backref=db.backref("packages", lazy=True))

	releases = db.relationship("PackageRelease", backref="package",
			lazy="dynamic", order_by=db.desc("package_release_releaseDate"))

	screenshots = db.relationship("PackageScreenshot", backref="package",
			lazy="dynamic", order_by=db.asc("package_screenshot_id"))

	requests = db.relationship("EditRequest", backref="package",
			lazy="dynamic")

	maintainers = db.relationship("User", secondary=maintainers, lazy="subquery")

	def __init__(self, package=None):
		if package is None:
			return

		self.author_id = package.author_id
		self.created_at = package.created_at
		self.state = package.state

		self.maintainers.append(self.author)

		for e in PackagePropertyKey:
			setattr(self, e.name, getattr(package, e.name))

	def getId(self):
		return "{}/{}".format(self.author.username, self.name)

	def getIsFOSS(self):
		return self.license.is_foss and self.media_license.is_foss

	def getIsOnGitHub(self):
		if self.repo is None:
			return False

		url = urlparse(self.repo)
		return url.netloc == "github.com"

	def getGitHubFullName(self):
		if self.repo is None:
			return None

		url = urlparse(self.repo)
		if url.netloc != "github.com":
			return None

		import re
		m = re.search(r"^\/([^\/]+)\/([^\/]+)\/?$", url.path)
		if m is None:
			return

		user = m.group(1)
		repo = m.group(2).replace(".git", "")

		return (user,repo)

	def getSortedDependencies(self, is_hard=None):
		query = self.dependencies
		if is_hard is not None:
			query = query.filter_by(optional=not is_hard)

		deps = query.all()
		deps.sort(key = lambda x: x.getName())
		return deps

	def getSortedHardDependencies(self):
		return self.getSortedDependencies(True)

	def getSortedOptionalDependencies(self):
		return self.getSortedDependencies(False)

	def getAsDictionaryKey(self):
		return {
			"name": self.name,
			"author": self.author.display_name,
			"type": self.type.toName(),
		}

	def getAsDictionaryShort(self, base_url, version=None):
		tnurl = self.getThumbnailURL(1)
		release = self.getDownloadRelease(version=version)
		return {
			"name": self.name,
			"title": self.title,
			"author": self.author.username,
			"short_description": self.short_desc,
			"type": self.type.toName(),
			"release": release and release.id,
			"thumbnail": (base_url + tnurl) if tnurl is not None else None
		}

	def getAsDictionary(self, base_url, version=None):
		tnurl = self.getThumbnailURL(1)
		release = self.getDownloadRelease(version=version)
		return {
			"author": self.author.username,
			"name": self.name,
			"title": self.title,
			"short_description": self.short_desc,
			"desc": self.desc,
			"type": self.type.toName(),
			"created_at": self.created_at.isoformat(),

			"license": self.license.name,
			"media_license": self.media_license.name,

			"repo": self.repo,
			"website": self.website,
			"issue_tracker": self.issueTracker,
			"forums": self.forums,

			"provides": [x.name for x in self.provides],
			"thumbnail": (base_url + tnurl) if tnurl is not None else None,
			"screenshots": [base_url + ss.url for ss in self.screenshots],

			"url": base_url + self.getDownloadURL(),
			"release": release and release.id,

			"score": round(self.score * 10) / 10,
			"downloads": self.downloads
		}

	def getThumbnailURL(self, level=2):
		screenshot = self.screenshots.filter_by(approved=True).order_by(db.asc(PackageScreenshot.id)).first()
		return screenshot.getThumbnailURL(level) if screenshot is not None else None

	def getMainScreenshotURL(self, absolute=False):
		screenshot = self.screenshots.filter_by(approved=True).order_by(db.asc(PackageScreenshot.id)).first()
		if screenshot is None:
			return None

		if absolute:
			from app.utils import abs_url
			return abs_url(screenshot.url)
		else:
			return screenshot.url

	def getDetailsURL(self, absolute=False):
		if absolute:
			from app.utils import abs_url_for
			return abs_url_for("packages.view",
					author=self.author.username, name=self.name)
		else:
			return url_for("packages.view",
					author=self.author.username, name=self.name)

	def getShieldURL(self, type):
		from app.utils import abs_url_for
		return abs_url_for("packages.shield",
				author=self.author.username, name=self.name, type=type)

	def makeShield(self, type):
		return "[![ContentDB]({})]({})" \
			.format(self.getShieldURL(type), self.getDetailsURL(True))

	def getEditURL(self):
		return url_for("packages.create_edit",
				author=self.author.username, name=self.name)

	def getSetStateURL(self, state):
		if type(state) == str:
			state = PackageState[perm]
		elif type(state) != PackageState:
			raise Exception("Unknown state given to Package.canMoveToState()")

		return url_for("packages.move_to_state",
				author=self.author.username, name=self.name, state=state.name.lower())

	def getRemoveURL(self):
		return url_for("packages.remove",
				author=self.author.username, name=self.name)

	def getNewScreenshotURL(self):
		return url_for("packages.create_screenshot",
				author=self.author.username, name=self.name)

	def getCreateReleaseURL(self):
		return url_for("packages.create_release",
				author=self.author.username, name=self.name)

	def getCreateEditRequestURL(self):
		return url_for("create_edit_editrequest_page",
				author=self.author.username, name=self.name)

	def getBulkReleaseURL(self):
		return url_for("packages.bulk_change_release",
			author=self.author.username, name=self.name)

	def getDownloadURL(self):
		return url_for("packages.download",
				author=self.author.username, name=self.name)

	def getEditMaintainersURL(self):
		return url_for("packages.edit_maintainers",
				author=self.author.username, name=self.name)

	def getRemoveSelfMaintainerURL(self):
		return url_for("packages.remove_self_maintainers",
				author=self.author.username, name=self.name)

	def getUpdateFromReleaseURL(self):
		return url_for("packages.update_from_release",
				author=self.author.username, name=self.name)

	def getReviewURL(self):
		return url_for('packages.review',
				author=self.author.username, name=self.name)

	def getDownloadRelease(self, version=None):
		for rel in self.releases:
			if rel.approved and (version is None or
					((rel.min_rel is None or rel.min_rel_id <= version.id) and \
					(rel.max_rel is None or rel.max_rel_id >= version.id))):
				return rel

		return None

	def checkPerm(self, user, perm):
		if not user.is_authenticated:
			return False

		if type(perm) == str:
			perm = Permission[perm]
		elif type(perm) != Permission:
			raise Exception("Unknown permission given to Package.checkPerm()")

		isOwner = user == self.author
		isMaintainer = isOwner or user.rank.atLeast(UserRank.EDITOR) or user in self.maintainers

		if perm == Permission.CREATE_THREAD:
			return user.rank.atLeast(UserRank.MEMBER)

		# Members can edit their own packages, and editors can edit any packages
		elif perm == Permission.MAKE_RELEASE or perm == Permission.ADD_SCREENSHOTS:
			return isMaintainer

		elif perm == Permission.EDIT_PACKAGE or \
				perm == Permission.APPROVE_CHANGES or perm == Permission.APPROVE_RELEASE:
			return isMaintainer and user.rank.atLeast(UserRank.MEMBER if self.approved else UserRank.NEW_MEMBER)

		# Anyone can change the package name when not approved, but only editors when approved
		elif perm == Permission.CHANGE_NAME:
			return not self.approved or user.rank.atLeast(UserRank.EDITOR)

		# Editors can change authors and approve new packages
		elif perm == Permission.APPROVE_NEW or perm == Permission.CHANGE_AUTHOR:
			return user.rank.atLeast(UserRank.EDITOR)

		elif perm == Permission.APPROVE_SCREENSHOT:
			return isMaintainer and user.rank.atLeast(UserRank.TRUSTED_MEMBER if self.approved else UserRank.NEW_MEMBER)

		elif perm == Permission.EDIT_MAINTAINERS:
			return isOwner or user.rank.atLeast(UserRank.MODERATOR)

		elif perm == Permission.UNAPPROVE_PACKAGE or perm == Permission.DELETE_PACKAGE:
			return user.rank.atLeast(UserRank.MEMBER if isOwner else UserRank.EDITOR)

		elif perm == Permission.CHANGE_RELEASE_URL:
			return user.rank.atLeast(UserRank.MODERATOR)

		elif perm == Permission.REIMPORT_META:
			return user.rank.atLeast(UserRank.ADMIN)

		else:
			raise Exception("Permission {} is not related to packages".format(perm.name))


	def canMoveToState(self, user, state):
		if not user.is_authenticated:
			return False

		if type(state) == str:
			state = PackageState[perm]
		elif type(state) != PackageState:
			raise Exception("Unknown state given to Package.canMoveToState()")

		if state not in PACKAGE_STATE_FLOW[self.state]:
			return False

		if state == PackageState.READY_FOR_REVIEW or state == PackageState.APPROVED:
			requiredPerm = Permission.APPROVE_NEW if state == PackageState.APPROVED else Permission.EDIT_PACKAGE

			if not self.checkPerm(user, requiredPerm):
				return False

			if state == PackageState.APPROVED and \
					("Other" in self.license.name or "Other" in self.media_license.name):
				return False

			needsScreenshot = \
				(self.type == self.type.GAME or self.type == self.type.TXP) and \
					self.screenshots.count() == 0
			return self.releases.count() > 0 and not needsScreenshot

		elif state == PackageState.CHANGES_NEEDED:
			return self.checkPerm(user, Permission.APPROVE_NEW)

		elif state == PackageState.WIP:
			return self.checkPerm(user, Permission.EDIT_PACKAGE) and \
				(user in self.maintainers or user.rank.atLeast(UserRank.ADMIN))

		return True


	def getNextStates(self, user):
		states = []

		for state in PackageState:
			if self.canMoveToState(user, state):
				states.append(state)

		return states


	def getScoreDict(self):
		return {
			"author": self.author.username,
			"name": self.name,
			"score": self.score,
			"score_downloads": self.score_downloads,
			"score_reviews": self.score - self.score_downloads,
			"downloads": self.downloads
		}

	def recalcScore(self):
		review_scores = [ 100 * r.asSign() for r in self.reviews ]
		self.score = self.score_downloads + sum(review_scores)


class MetaPackage(db.Model):
	id           = db.Column(db.Integer, primary_key=True)
	name         = db.Column(db.String(100), unique=True, nullable=False)
	dependencies = db.relationship("Dependency", backref="meta_package", lazy="dynamic")

	mp_name_valid = db.CheckConstraint("name ~* '^[a-z0-9_]+$'")

	def __init__(self, name=None):
		self.name = name

	def __str__(self):
		return self.name

	@staticmethod
	def ListToSpec(list):
		return ",".join([str(x) for x in list])

	@staticmethod
	def GetOrCreate(name, cache={}):
		mp = cache.get(name)
		if mp is None:
			mp = MetaPackage.query.filter_by(name=name).first()

		if mp is None:
			mp = MetaPackage(name)
			db.session.add(mp)

		cache[name] = mp
		return mp

	@staticmethod
	def SpecToList(spec, cache={}):
		retval = []
		arr = spec.split(",")

		import re
		pattern = re.compile("^([a-z0-9_]+)$")

		for x in arr:
			x = x.strip()
			if x == "":
				continue

			if not pattern.match(x):
				continue

			retval.append(MetaPackage.GetOrCreate(x, cache))

		return retval


class ContentWarning(db.Model):
	id              = db.Column(db.Integer, primary_key=True)
	name            = db.Column(db.String(100), unique=True, nullable=False)
	title           = db.Column(db.String(100), nullable=False)
	description     = db.Column(db.String(500), nullable=False)

	def __init__(self, title, description=""):
		self.title       = title
		self.description = description

		import re
		regex = re.compile("[^a-z_]")
		self.name = regex.sub("", self.title.lower().replace(" ", "_"))


class Tag(db.Model):
	id              = db.Column(db.Integer, primary_key=True)
	name            = db.Column(db.String(100), unique=True, nullable=False)
	title           = db.Column(db.String(100), nullable=False)
	description     = db.Column(db.String(500), nullable=True, default=None)
	backgroundColor = db.Column(db.String(6), nullable=False)
	textColor       = db.Column(db.String(6), nullable=False)
	views           = db.Column(db.Integer, nullable=False, default=0)

	def __init__(self, title, backgroundColor="000000", textColor="ffffff"):
		self.title           = title
		self.backgroundColor = backgroundColor
		self.textColor       = textColor

		import re
		regex = re.compile("[^a-z_]")
		self.name = regex.sub("", self.title.lower().replace(" ", "_"))


class MinetestRelease(db.Model):
	id       = db.Column(db.Integer, primary_key=True)
	name     = db.Column(db.String(100), unique=True, nullable=False)
	protocol = db.Column(db.Integer, nullable=False, default=0)

	def __init__(self, name=None, protocol=0):
		self.name = name
		self.protocol = protocol

	def getActual(self):
		return None if self.name == "None" else self

	@classmethod
	def get(cls, version, protocol_num):
		if version:
			parts = version.strip().split(".")
			if len(parts) >= 2:
				major_minor = parts[0] + "." + parts[1]
				query = MinetestRelease.query.filter(MinetestRelease.name.like("{}%".format(major_minor)))
				if protocol_num:
					query = query.filter_by(protocol=protocol_num)

				release = query.one_or_none()
				if release:
					return release

		if protocol_num:
			return MinetestRelease.query.filter_by(protocol=protocol_num).first()

		return None


class PackageRelease(db.Model):
	id           = db.Column(db.Integer, primary_key=True)

	package_id   = db.Column(db.Integer, db.ForeignKey("package.id"))
	title        = db.Column(db.String(100), nullable=False)
	releaseDate  = db.Column(db.DateTime,    nullable=False)
	url          = db.Column(db.String(200), nullable=False)
	approved     = db.Column(db.Boolean, nullable=False, default=False)
	task_id      = db.Column(db.String(37), nullable=True)
	commit_hash  = db.Column(db.String(41), nullable=True, default=None)
	downloads    = db.Column(db.Integer, nullable=False, default=0)

	min_rel_id = db.Column(db.Integer, db.ForeignKey("minetest_release.id"), nullable=True, server_default=None)
	min_rel    = db.relationship("MinetestRelease", foreign_keys=[min_rel_id])

	max_rel_id = db.Column(db.Integer, db.ForeignKey("minetest_release.id"), nullable=True, server_default=None)
	max_rel    = db.relationship("MinetestRelease", foreign_keys=[max_rel_id])

	# If the release is approved, then the task_id must be null and the url must be present
	CK_approval_valid = db.CheckConstraint("not approved OR (task_id IS NULL AND (url = '') IS NOT FALSE)")

	def getAsDictionary(self):
		return {
			"id": self.id,
			"title": self.title,
			"url": self.url if self.url != "" else None,
			"release_date": self.releaseDate.isoformat(),
			"commit": self.commit_hash,
			"downloads": self.downloads,
			"min_protocol": self.min_rel and self.min_rel.protocol,
			"max_protocol": self.max_rel and self.max_rel.protocol
		}

	def getEditURL(self):
		return url_for("packages.edit_release",
				author=self.package.author.username,
				name=self.package.name,
				id=self.id)

	def getDeleteURL(self):
		return url_for("packages.delete_release",
				author=self.package.author.username,
				name=self.package.name,
				id=self.id)

	def getDownloadURL(self):
		return url_for("packages.download_release",
				author=self.package.author.username,
				name=self.package.name,
				id=self.id)

	def __init__(self):
		self.releaseDate = datetime.datetime.now()

	def approve(self, user):
		if not self.package.checkPerm(user, Permission.APPROVE_RELEASE):
			return False

		assert self.task_id is None and self.url is not None and self.url != ""

		self.approved = True
		return True

	def checkPerm(self, user, perm):
		if not user.is_authenticated:
			return False

		if type(perm) == str:
			perm = Permission[perm]
		elif type(perm) != Permission:
			raise Exception("Unknown permission given to PackageRelease.checkPerm()")

		isOwner = user == self.package.author

		if perm == Permission.DELETE_RELEASE:
			if user.rank.atLeast(UserRank.ADMIN):
				return True

			if not (isOwner or user.rank.atLeast(UserRank.EDITOR)):
				return False

			if not self.package.approved or self.task_id is not None:
				return True

			count = PackageRelease.query \
					.filter_by(package_id=self.package_id) \
					.filter(PackageRelease.id > self.id) \
					.count()

			return count > 0
		else:
			raise Exception("Permission {} is not related to releases".format(perm.name))


# class PackageReview(db.Model):
# 	id         = db.Column(db.Integer, primary_key=True)
# 	package_id = db.Column(db.Integer, db.ForeignKey("package.id"))
# 	thread_id  = db.Column(db.Integer, db.ForeignKey("thread.id"), nullable=False)
# 	recommend  = db.Column(db.Boolean, nullable=False, default=True)


class PackageScreenshot(db.Model):
	id         = db.Column(db.Integer, primary_key=True)
	package_id = db.Column(db.Integer, db.ForeignKey("package.id"))
	title      = db.Column(db.String(100), nullable=False)
	url        = db.Column(db.String(100), nullable=False)
	approved   = db.Column(db.Boolean, nullable=False, default=False)


	def getEditURL(self):
		return url_for("packages.edit_screenshot",
				author=self.package.author.username,
				name=self.package.name,
				id=self.id)

	def getThumbnailURL(self, level=2):
		return self.url.replace("/uploads/", ("/thumbnails/{:d}/").format(level))


class APIToken(db.Model):
	id           = db.Column(db.Integer, primary_key=True)
	access_token = db.Column(db.String(34), unique=True)

	name         = db.Column(db.String(100), nullable=False)
	owner_id     = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
	# owner is created using backref

	created_at   = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)

	package_id = db.Column(db.Integer, db.ForeignKey("package.id"), nullable=True)
	package    = db.relationship("Package", foreign_keys=[package_id])

	def canOperateOnPackage(self, package):
		if self.package and self.package != package:
			return False

		return package.author == self.owner


class EditRequest(db.Model):
	id           = db.Column(db.Integer, primary_key=True)

	package_id   = db.Column(db.Integer, db.ForeignKey("package.id"))
	author_id    = db.Column(db.Integer, db.ForeignKey("user.id"))

	title        = db.Column(db.String(100), nullable=False)
	desc         = db.Column(db.String(1000), nullable=True)

	# 0 - open
	# 1 - merged
	# 2 - rejected
	status       = db.Column(db.Integer, nullable=False, default=0)

	changes = db.relationship("EditRequestChange", backref="request",
			lazy="dynamic")

	def getURL(self):
		return url_for("view_editrequest_page",
				author=self.package.author.username,
				name=self.package.name,
				id=self.id)

	def getApproveURL(self):
		return url_for("approve_editrequest_page",
				author=self.package.author.username,
				name=self.package.name,
				id=self.id)

	def getRejectURL(self):
		return url_for("reject_editrequest_page",
				author=self.package.author.username,
				name=self.package.name,
				id=self.id)

	def getEditURL(self):
		return url_for("create_edit_editrequest_page",
				author=self.package.author.username,
				name=self.package.name,
				id=self.id)

	def applyAll(self, package):
		for change in self.changes:
			change.apply(package)


	def checkPerm(self, user, perm):
		if not user.is_authenticated:
			return False

		if type(perm) == str:
			perm = Permission[perm]
		elif type(perm) != Permission:
			raise Exception("Unknown permission given to EditRequest.checkPerm()")

		isOwner = user == self.author

		# Members can edit their own packages, and editors can edit any packages
		if perm == Permission.EDIT_EDITREQUEST:
			return isOwner or user.rank.atLeast(UserRank.EDITOR)

		else:
			raise Exception("Permission {} is not related to packages".format(perm.name))




class EditRequestChange(db.Model):
	id           = db.Column(db.Integer, primary_key=True)

	request_id   = db.Column(db.Integer, db.ForeignKey("edit_request.id"))
	key          = db.Column(db.Enum(PackagePropertyKey), nullable=False)

	# TODO: make diff instead
	oldValue     = db.Column(db.Text, nullable=True)
	newValue     = db.Column(db.Text, nullable=True)

	def apply(self, package):
		if self.key == PackagePropertyKey.tags:
			package.tags.clear()
			for tagTitle in self.newValue.split(","):
				tag = Tag.query.filter_by(title=tagTitle.strip()).first()
				package.tags.append(tag)

		else:
			setattr(package, self.key.name, self.newValue)


watchers = db.Table("watchers",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("thread_id", db.Integer, db.ForeignKey("thread.id"), primary_key=True)
)

class Thread(db.Model):
	id         = db.Column(db.Integer, primary_key=True)

	package_id = db.Column(db.Integer, db.ForeignKey("package.id"), nullable=True)
	package    = db.relationship("Package", foreign_keys=[package_id])

	review_id  = db.Column(db.Integer, db.ForeignKey("package_review.id"), nullable=True)
	review     = db.relationship("PackageReview", foreign_keys=[review_id])

	author_id  = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
	title      = db.Column(db.String(100), nullable=False)
	private    = db.Column(db.Boolean, server_default="0", nullable=False)

	locked     = db.Column(db.Boolean, server_default="0", nullable=False)

	created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)

	replies    = db.relationship("ThreadReply", backref="thread", lazy="dynamic", \
			order_by=db.asc("thread_reply_id"))

	watchers   = db.relationship("User", secondary=watchers, lazy="subquery", \
			backref=db.backref("watching", lazy=True))

	def getViewURL(self):
		return url_for("threads.view", id=self.id)

	def getSubscribeURL(self):
		return url_for("threads.subscribe", id=self.id)

	def getUnsubscribeURL(self):
		return url_for("threads.unsubscribe", id=self.id)

	def checkPerm(self, user, perm):
		if not user.is_authenticated:
			return perm == Permission.SEE_THREAD and not self.private

		if type(perm) == str:
			perm = Permission[perm]
		elif type(perm) != Permission:
			raise Exception("Unknown permission given to Thread.checkPerm()")

		isMaintainer = user == self.author or (self.package is not None and self.package.author == user)
		if self.package:
			isMaintainer = isMaintainer or user in self.package.maintainers

		canSee = not self.private or isMaintainer or user.rank.atLeast(UserRank.EDITOR)

		if perm == Permission.SEE_THREAD:
			return canSee

		elif perm == Permission.COMMENT_THREAD:
			return canSee and (not self.locked or user.rank.atLeast(UserRank.MODERATOR))

		elif perm == Permission.LOCK_THREAD:
			return user.rank.atLeast(UserRank.MODERATOR)

		else:
			raise Exception("Permission {} is not related to threads".format(perm.name))

class ThreadReply(db.Model):
	id         = db.Column(db.Integer, primary_key=True)
	thread_id  = db.Column(db.Integer, db.ForeignKey("thread.id"), nullable=False)
	comment    = db.Column(db.String(2000), nullable=False)
	author_id  = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
	created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)

	def checkPerm(self, user, perm):
		if not user.is_authenticated:
			return False

		if type(perm) == str:
			perm = Permission[perm]
		elif type(perm) != Permission:
			raise Exception("Unknown permission given to ThreadReply.checkPerm()")

		if perm == Permission.EDIT_REPLY:
			return user == self.author and user.rank.atLeast(UserRank.MEMBER) and not self.thread.locked

		elif perm == Permission.DELETE_REPLY:
			return user.rank.atLeast(UserRank.MODERATOR) and self.thread.replies[0] != self

		else:
			raise Exception("Permission {} is not related to threads".format(perm.name))


class PackageReview(db.Model):
	id         = db.Column(db.Integer, primary_key=True)

	package_id = db.Column(db.Integer, db.ForeignKey("package.id"), nullable=True)
	package    = db.relationship("Package", foreign_keys=[package_id], backref=db.backref("reviews", lazy=True))

	created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)

	author_id  = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
	author     = db.relationship("User", foreign_keys=[author_id], backref=db.backref("reviews", lazy=True))

	recommends = db.Column(db.Boolean, nullable=False)

	thread     = db.relationship("Thread", uselist=False, back_populates="review")

	def asSign(self):
		return 1 if self.recommends else -1

	def getEditURL(self):
		return self.package.getReviewURL()

	def getDeleteURL(self):
		return url_for("packages.delete_review",
				author=self.package.author.username,
				name=self.package.name)


class AuditSeverity(enum.Enum):
	NORMAL = 0 # Normal user changes
	EDITOR = 1 # Editor changes
	MODERATION = 2 # Destructive / moderator changes

	def __str__(self):
		return self.name

	def getTitle(self):
		return self.name.replace("_", " ").title()

	@classmethod
	def choices(cls):
		return [(choice, choice.getTitle()) for choice in cls]

	@classmethod
	def coerce(cls, item):
		return item if type(item) == AuditSeverity else AuditSeverity[item]



class AuditLogEntry(db.Model):
	id         = db.Column(db.Integer, primary_key=True)

	created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)

	causer_id  = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
	causer     = db.relationship("User", foreign_keys=[causer_id])

	severity   = db.Column(db.Enum(AuditSeverity), nullable=False)

	title      = db.Column(db.String(100), nullable=False)
	url        = db.Column(db.String(200), nullable=True)

	package_id = db.Column(db.Integer, db.ForeignKey("package.id"), nullable=True)
	package    = db.relationship("Package", foreign_keys=[package_id])

	description = db.Column(db.Text, nullable=True, default=None)

	def __init__(self, causer, severity, title, url, package=None, description=None):
		if len(title) > 100:
			title = title[:99] + "…"

		self.causer   = causer
		self.severity = severity
		self.title    = title
		self.url      = url
		self.package  = package
		self.description = description




REPO_BLACKLIST = [".zip", "mediafire.com", "dropbox.com", "weebly.com", \
		"minetest.net", "dropboxusercontent.com", "4shared.com", \
		"digitalaudioconcepts.com", "hg.intevation.org", "www.wtfpl.net", \
		"imageshack.com", "imgur.com"]

class ForumTopic(db.Model):
	topic_id  = db.Column(db.Integer, primary_key=True, autoincrement=False)
	author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
	author    = db.relationship("User")

	wip       = db.Column(db.Boolean, server_default="0")
	discarded = db.Column(db.Boolean, server_default="0")

	type      = db.Column(db.Enum(PackageType), nullable=False)
	title     = db.Column(db.String(200), nullable=False)
	name      = db.Column(db.String(30), nullable=True)
	link      = db.Column(db.String(200), nullable=True)

	posts     = db.Column(db.Integer, nullable=False)
	views     = db.Column(db.Integer, nullable=False)

	created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)

	def getRepoURL(self):
		if self.link is None:
			return None

		for item in REPO_BLACKLIST:
			if item in self.link:
				return None

		return self.link.replace("repo.or.cz/w/", "repo.or.cz/")

	def getAsDictionary(self):
		return {
			"author": self.author.username,
			"name":   self.name,
			"type":   self.type.toName(),
			"title":  self.title,
			"id":     self.topic_id,
			"link":   self.link,
			"posts":  self.posts,
			"views":  self.views,
			"is_wip": self.wip,
			"discarded":  self.discarded,
			"created_at": self.created_at.isoformat(),
		}

	def checkPerm(self, user, perm):
		if not user.is_authenticated:
			return False

		if type(perm) == str:
			perm = Permission[perm]
		elif type(perm) != Permission:
			raise Exception("Unknown permission given to ForumTopic.checkPerm()")

		if perm == Permission.TOPIC_DISCARD:
			return self.author == user or user.rank.atLeast(UserRank.EDITOR)

		else:
			raise Exception("Permission {} is not related to topics".format(perm.name))


# Setup Flask-User
user_manager = UserManager(app, db, User)

if app.config.get("LOG_SQL"):
	import logging
	logging.basicConfig()
	logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
