{{/*
Image reference for a Robot Shop service, pinned by digest when one is set.
Call with (list $ "rs-cart"). Produces e.g.
  robotshop/rs-cart:2.1.0@sha256:...
The digests in values.yaml belong to image.version 2.1.0. If you change the
version, update or remove the digests, or the image will not match.
*/}}
{{- define "robot-shop.image" -}}
{{- $root := index . 0 -}}
{{- $name := index . 1 -}}
{{- $digests := $root.Values.image.digests | default dict -}}
{{- $digest := index $digests $name | default "" -}}
{{- printf "%s/%s:%s" $root.Values.image.repo $name $root.Values.image.version -}}
{{- if $digest }}@{{ $digest }}{{ end -}}
{{- end -}}
