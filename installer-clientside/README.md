# Building the installer

This is sort of a mess.  Make sure to do things in roughly exactly this
order.  Otherwise things will go wrong.  If you understand Node release
engineering I want to hear from you.  Actually I don't, I just want a PR for
it.  Thanks.

* `pushd x1p-js; npm i; npm run build; popd`
* `pushd ../; make; ln -s ...whatever.../latest.x1p; popd`
* `pushd install-gui; npm i; bash pack-em-all.sh; popd`
