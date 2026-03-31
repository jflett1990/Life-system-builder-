{pkgs}: {
  deps = [
    pkgs.chromium
    pkgs.xorg.libXcomposite
    pkgs.xorg.libXtst
    pkgs.xorg.libXrender
    pkgs.xorg.libXi
    pkgs.xorg.libXext
    pkgs.xorg.libXcursor
    pkgs.xorg.libX11
    pkgs.pango
    pkgs.mesa
    pkgs.libxkbcommon
    pkgs.libdrm
    pkgs.gtk3
    pkgs.glib
    pkgs.fontconfig
    pkgs.expat
    pkgs.dbus
    pkgs.cups
    pkgs.atk
    pkgs.alsa-lib
    pkgs.nss
    pkgs.nspr
  ];
}
