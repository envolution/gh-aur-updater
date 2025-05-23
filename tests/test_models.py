"""
tests/test_models.py - Unit tests for data models.
"""
import pytest
from gh-aur-updater.models import PkgVersion, PKGBUILDData # Add other models as needed
from pathlib import Path

class TestPkgVersion:
    def test_creation_and_str(self):
        pv1 = PkgVersion(pkgver="1.2.3", pkgrel="1")
        assert str(pv1) == "1.2.3-1"

        pv2 = PkgVersion(pkgver="2.0", pkgrel="10", epoch="2")
        assert str(pv2) == "2:2.0-10"

        pv3 = PkgVersion(pkgver="3.0", pkgrel="1", epoch=None) # Explicit None
        assert str(pv3) == "3.0-1"
        
        pv4 = PkgVersion(pkgver="nobuild", pkgrel="custom")
        assert str(pv4) == "nobuild-custom"


    def test_from_string_parsing(self):
        pv = PkgVersion.from_string("1.2.3-1")
        assert pv.epoch is None
        assert pv.pkgver == "1.2.3"
        assert pv.pkgrel == "1"

        pv = PkgVersion.from_string("2:3.4.5-6")
        assert pv.epoch == "2"
        assert pv.pkgver == "3.4.5"
        assert pv.pkgrel == "6"

        pv = PkgVersion.from_string("7.8.9") # No release, should default
        assert pv.epoch is None
        assert pv.pkgver == "7.8.9"
        assert pv.pkgrel == "1" # Default pkgrel

        pv = PkgVersion.from_string("3:10.0") # Epoch, no release
        assert pv.epoch == "3"
        assert pv.pkgver == "10.0"
        assert pv.pkgrel == "1"

        pv = PkgVersion.from_string("my-complex-pkgver-1.2-customRel_beta")
        assert pv.epoch is None
        assert pv.pkgver == "my-complex-pkgver-1.2"
        assert pv.pkgrel == "customRel_beta"

        pv = PkgVersion.from_string("1:another-complex.pkgver-1.2.3-rc1-5")
        assert pv.epoch == "1"
        assert pv.pkgver == "another-complex.pkgver-1.2.3-rc1"
        assert pv.pkgrel == "5"

# ...
class TestPKGBUILDData:
    def test_display_name(self):
        data1 = PKGBUILDData(pkgbuild_path=Path("."), pkgbase="mybase")
        assert data1.display_name == "mybase"

        data2 = PKGBUILDData(pkgbuild_path=Path("."), pkgname=["mypkg"], pkgbase="mypkg") # Provide pkgbase
        assert data2.display_name == "mypkg" # pkgbase takes precedence if different from pkgname[0]

        data3 = PKGBUILDData(pkgbuild_path=Path("."), pkgname=["splitpkgA", "splitpkgB"], pkgbase="basepkg")
        assert data3.display_name == "basepkg"
        
        # Test default/empty case
        data4 = PKGBUILDData(pkgbuild_path=Path(".")) # Now uses default for pkgbase
        assert data4.display_name == "UnknownPackage" # As pkgbase is "" and pkgname is []
        data5 = PKGBUILDData(pkgbuild_path=Path("."), pkgname=["onlypkgname"]) # pkgbase defaults to ""
        assert data5.display_name == "onlypkgname" # display_name should use pkgname[0] if pkgbase is empty

    def test_current_version_obj(self):
        data = PKGBUILDData(pkgbuild_path=Path("."), pkgver="1.0", pkgrel="2", epoch="1", pkgbase="test")
        version_obj = data.current_version_obj
        assert isinstance(version_obj, PkgVersion)
        assert str(version_obj) == "1:1.0-2"
