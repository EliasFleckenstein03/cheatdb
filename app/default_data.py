from .models import *
from .utils import make_flask_user_password


def populate(session):
	admin_user = User("Fleckenstein")
	admin_user.active = True
	admin_user.password = make_flask_user_password("tuckfrump")
	admin_user.github_username = "EliasFleckenstein03"
	admin_user.forums_username = "Fleckenstein"
	admin_user.rank = UserRank.ADMIN
	session.add(admin_user)

	tags = {}
	for tag in ["Render", "World", "Player", \
			"Chat", "Exploit", "Inventory", "Movement", \
			"Combat", "Bot", "GUI", \
			"MineClone", "Any Game", "CTF", "Minetest Game"]:
		row = Tag(tag)
		tags[row.name] = row
		session.add(row)

	licenses = {}
	for license in ["GPLv2.1", "GPLv3", "LGPLv2.1", "LGPLv3", "AGPLv2.1", "AGPLv3",
					"Apache", "BSD 3-Clause", "BSD 2-Clause", "CC0", "CC-BY-SA",
					"CC-BY", "MIT", "ZLib", "Other (Free)"]:
		row = License(license)
		licenses[row.name] = row
		session.add(row)

	for license in ["CC-BY-NC-SA", "Other (Non-free)"]:
		row = License(license, False)
		licenses[row.name] = row
		session.add(row)


def populate_test_data(session):
	licenses = { x.name : x for x in License.query.all() }
	tags = { x.name : x for x in Tag.query.all() }
	admin_user = User.query.filter_by(rank=UserRank.ADMIN).first()

	cora = User("cora")
	cora.github_username = "corarona"
	cora.rank = UserRank.EDITOR
	session.add(cora)

	not1 = Notification(admin_user, cora, "Schematicas Approved", "/packages/Fleckenstein/schematicas/")
	session.add(not1)

	anon5 = User("anon5")
	anon5.github_username = "anon55555"
	session.add(anon5)

	mod = Package()
	mod.state = PackageState.APPROVED
	mod.name = "perlin"
	mod.title = "Perlin Terraforming"
	mod.license = licenses["GPLv3"]
	mod.media_license = licenses["GPLv3"]
	mod.type = PackageType.MOD
	mod.author = admin_user
	mod.tags.append(tags["world"])
	mod.tags.append(tags["any_game"])
	mod.repo = "https://github.com/EliasFleckenstein03/perlin"
	mod.issueTracker = "https://github.com/EliasFleckenstein03/perlin/issues"
	mod.short_desc = "A dragonfire CSM that does terraforming automatically using perlin noise."
	mod.desc = ""
	session.add(mod)

	rel = PackageRelease()
	rel.package = mod
	rel.title = "v1.0.0"
	rel.url = "https://github.com/EliasFleckenstein03/perlin/archive/master.zip"
	rel.approved = True
	session.add(rel)

	mod = Package()
	mod.state = PackageState.APPROVED
	mod.name = "warp"
	mod.title = "Warps"
	mod.license = licenses["GPLv3"]
	mod.media_license = licenses["GPLv3"]
	mod.type = PackageType.MOD
	mod.author = admin_user
	mod.tags.append(tags["movement"])
	mod.tags.append(tags["exploit"])
	mod.tags.append(tags["gui"])
	mod.tags.append(tags["any_game"])
	mod.repo = "https://github.com/EliasFleckenstein03/warp"
	mod.issueTracker = "https://github.com/EliasFleckenstein03/warp/issues"
	mod.short_desc = "A dragonfire CSM to set warps in the world and use the teleport exploit."
	mod.desc = ""
	session.add(mod)

	rel = PackageRelease()
	rel.package = mod
	rel.title = "v1.0.0"
	rel.url = "https://github.com/EliasFleckenstein03/warp/archive/master.zip"
	rel.approved = True
	session.add(rel)

	mod = Package()
	mod.state = PackageState.APPROVED
	mod.name = "pathfinding"
	mod.title = "Pathfinding"
	mod.license = licenses["GPLv3"]
	mod.media_license = licenses["GPLv3"]
	mod.type = PackageType.MOD
	mod.author = admin_user
	mod.tags.append(tags["movement"])
	mod.tags.append(tags["bot"])
	mod.tags.append(tags["any_game"])
	mod.repo = "https://github.com/EliasFleckenstein03/pathfinding"
	mod.issueTracker = "https://github.com/EliasFleckenstein03/pathfinding/issues"
	mod.short_desc = "A dragonfire CSM that adds .goto command."
	mod.desc = ""
	session.add(mod)

	rel = PackageRelease()
	rel.package = mod
	rel.title = "v1.0.0"
	rel.url = "https://github.com/EliasFleckenstein03/pathfinding/archive/master.zip"
	rel.approved = True
	session.add(rel)

	mod = Package()
	mod.state = PackageState.APPROVED
	mod.name = "schematicas"
	mod.title = "Schematicas"
	mod.license = licenses["GPLv3"]
	mod.media_license = licenses["GPLv3"]
	mod.type = PackageType.MOD
	mod.author = admin_user
	mod.tags.append(tags["world"])
	mod.tags.append(tags["bot"])
	mod.tags.append(tags["any_game"])
	mod.repo = "https://github.com/EliasFleckenstein03/schematicas/"
	mod.issueTracker = "https://github.com/EliasFleckenstein03/schematicas/issues"
	mod.short_desc = "Dragonfire CSM for saving structures and building them automatically."
	mod.desc = ""
	session.add(mod)
	
	rel = PackageRelease()
	rel.package = mod
	rel.title = "v1.0.0"
	rel.url = "https://github.com/EliasFleckenstein03/schematicas/archive/master.zip"
	rel.approved = True
	session.add(rel)
	
	txp = Package()
	txp.state = PackageState.APPROVED
	txp.name = "mc_textures"
	txp.title = "Minecraft Textures"
	txp.license = licenses["Other (Non-free)"]
	txp.media_license = licenses["Other (Non-free)"]
	txp.type = PackageType.TXP
	txp.author = admin_user
	txp.tags.append(tags["mineclone"])
	txp.repo = "https://github.com/EliasFleckenstein03/mc-textures/"
	txp.issueTracker = "https://github.com/EliasFleckenstein03/mc-textures/issues"
	txp.short_desc = "MineClone2 Texture Pack containing the original minecraft textures."
	txp.desc = ""
	session.add(txp)
	
	rel = PackageRelease()
	rel.package = txp
	rel.title = "v1.0.0"
	rel.url = "https://github.com/EliasFleckenstein03/mc-textures/master.zip"
	rel.approved = True
	session.add(rel)

	

	session.commit()

	metas = {}
	for package in Package.query.filter_by(type=PackageType.MOD).all():
		meta = None
		try:
			meta = metas[package.name]
		except KeyError:
			meta = MetaPackage(package.name)
			session.add(meta)
			metas[package.name] = meta
		package.provides.append(meta)
