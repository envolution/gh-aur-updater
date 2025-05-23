pkgname=gh-aur-updater
pkgver=0.1.0
pkgrel=1
pkgdesc="GitHub-integrated AUR package updater"
arch=('any')
url="https://github.com/envolution/gh-aur-updater"
license=('MIT')
depends=('python' 'python-requests')
makedepends=('python-build' 'python-installer' 'python-wheel' 'python-setuptools'
	python-pytest python-responses git)
source=("git+$url.git")
noextract=("$pkgname")
sha256sums=('SKIP')

build() {
    python -m build --wheel --no-isolation
}

package() {
    python -m installer --destdir="$pkgdir" dist/*.whl
}
