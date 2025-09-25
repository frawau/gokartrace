#!/usr/bin/env python3
"""
Asset installation script for Go-Kart Race application.
Downloads and installs required flags and fonts.
"""

import os
import sys
import urllib.request
import zipfile
import tempfile
import shutil
from pathlib import Path


def ensure_dir(path):
    """Create directory if it doesn't exist."""
    Path(path).mkdir(parents=True, exist_ok=True)


def download_file(url, destination):
    """Download a file from URL to destination."""
    print(f"Downloading {url}...")
    try:
        urllib.request.urlretrieve(url, destination)
        print(f"Downloaded to {destination}")
        return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return False


def download_google_fonts():
    """Download Google Noto fonts."""
    fonts = {
        "NotoSans-Regular.ttf": "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf",
        "NotoSansJP-Regular.ttf": "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/Japanese/NotoSansJP-Regular.otf",
        "NotoSansKR-Regular.ttf": "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/Korean/NotoSansKR-Regular.otf",
        "NotoSansTC-Regular.ttf": "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/TraditionalChinese/NotoSansTC-Regular.otf",
        "NotoSansThai-Regular.ttf": "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansThai/NotoSansThai-Regular.ttf",
    }

    font_dir = Path("/usr/local/share/fonts")
    ensure_dir(font_dir)

    for font_name, url in fonts.items():
        font_path = font_dir / font_name
        if not font_path.exists():
            if download_file(url, str(font_path)):
                print(f"✓ Installed font: {font_name}")
            else:
                print(f"✗ Failed to install font: {font_name}")
        else:
            print(f"✓ Font already exists: {font_name}")


def download_country_flags():
    """Download country flags from Flagpedia.net with fixed height."""
    import pycountry

    static_dir = Path("./static")
    flag_dir = static_dir / "flags"
    ensure_dir(flag_dir)

    # Flagpedia.net CDN URL pattern for fixed height flags (h240 = 240px height, largest under 512px)
    base_url = "https://flagcdn.com/h240"

    # Get all countries from pycountry
    countries = list(pycountry.countries)

    success_count = 0
    failed_countries = []

    print(
        f"Downloading {len(countries)} country flags from Flagpedia.net (240px height)..."
    )

    for country in countries:
        country_code = country.alpha_2.lower()
        flag_url = f"{base_url}/{country_code}.png"
        flag_path = flag_dir / f"{country_code}.png"

        if not flag_path.exists():
            if download_file(flag_url, str(flag_path)):
                success_count += 1
                print(f"✓ Downloaded flag: {country_code}.png ({country.name})")
            else:
                failed_countries.append(f"{country_code} ({country.name})")
        else:
            success_count += 1
            print(f"✓ Flag already exists: {country_code}.png")

    # Download UN flag as fallback
    un_flag_url = f"{base_url}/un.png"
    un_flag_path = flag_dir / "un.png"
    if not un_flag_path.exists():
        if download_file(un_flag_url, str(un_flag_path)):
            success_count += 1
            print("✓ Downloaded UN flag")
        else:
            print("✗ Failed to download UN flag")

    print(f"\n✓ Successfully installed {success_count} country flags")

    if failed_countries:
        print(f"✗ Failed to download {len(failed_countries)} flags:")
        for country in failed_countries[:10]:  # Show only first 10 failures
            print(f"  - {country}")
        if len(failed_countries) > 10:
            print(f"  ... and {len(failed_countries) - 10} more")


def create_fallback_flags():
    """Create simple fallback flags if downloads fail."""
    flag_dir = Path("./static/flags")
    ensure_dir(flag_dir)

    # Create a simple UN flag as fallback (solid blue with UN logo placeholder)
    un_flag = flag_dir / "un.png"
    if not un_flag.exists():
        print("Creating fallback UN flag...")
        # In a real scenario, you'd create a simple colored PNG here
        # For now, just create an empty file as placeholder
        un_flag.touch()


def main():
    """Main installation function."""
    print("Go-Kart Race Asset Installation")
    print("=" * 40)

    # Check if running as root for font installation
    if os.geteuid() != 0:
        print("Warning: Not running as root. Font installation may fail.")
        print("Consider running: sudo python3 install_assets.py")

    print("\n1. Installing fonts...")
    try:
        download_google_fonts()
    except Exception as e:
        print(f"Font installation failed: {e}")

    print("\n2. Installing country flags...")
    try:
        download_country_flags()
        create_fallback_flags()
    except Exception as e:
        print(f"Flag installation failed: {e}")

    print("\n3. Setting permissions...")
    try:
        # Update font cache
        os.system("fc-cache -fv")
        print("✓ Font cache updated")
    except Exception as e:
        print(f"Font cache update failed: {e}")

    print("\nInstallation complete!")
    print("\nNext steps:")
    print("1. Update FLAGDIR and LOGOIMG paths in race/pdfcardview.py")
    print("2. Ensure static files are properly configured")
    print("3. Test flag display in templates")


if __name__ == "__main__":
    main()
