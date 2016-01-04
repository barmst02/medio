Synology Static Photo Gallery (SPG)
====================================

Synchronizes comments from Synology Photo Station to your original images 
as EXIF, IPTC, and XMP attributes.  Exports galleries as self-contained HTML 
galleries. Synchronizes exported galleries to S3.

Take a look at the [wiki](https://bitbucket.org/polandj/synology-static-photo-gallery/wiki/Home) to learn more about this package.

You can install this package on your Synology by adding **http://synopkgs-garble.rhcloud.com** as a Package Source in **Package Center**.  NOTE:  My packages are not signed, so you may need to change the trust level setting in Package Center.  You can find this at **Package Center → Settings → General → Trust Level**, set it to any developer.

If you are interested in helping out with this project, please let me know, I will happily add collaborators.

Donations welcome: **128PqHs6hHLNXvBQaWYEbDowrTvrnRQ7df**.

Changelog
---------

1.16
 
 - Make compatible with DSM 5.1+
 - Fix Python path detection
 - Fix Postgres user 

1.15

 - Fix auth for DSM 4.3/5.0

1.14

 - bump version to 1.14
 - add favicon
 - fix compatibility with DSM 4.3 and PS6.  Thumbnails are now named with underscores instead of colons
 - fix issue with comments that are in double quotes       
 - fix issue #3: allow empty copyright
 - fix issue #5: don't error on export and S3 config if it's not enabled
 - add 2014 copyright
 
