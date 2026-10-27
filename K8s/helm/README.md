# Stan's Robot Shop

Use this helm chart to customise your install of Stan's Robot Shop.

### Helm v2.x

```shell
$ helm install --name robot-shop --namespace robot-shop .
```

### Helm v3.x

```bash
$ kubectl create ns robot-shop
$ helm install robot-shop --namespace robot-shop .
```

## Images

By default the images are pulled from Docker Hub. Setting `image.repo` this can be changed, for example:

```shell
$ helm install --set image.repo=eu.gcr.io/acme ...
```

Will pull images from the European Google registry project `acme`.

By default this fork pulls version 2.1.0, pinned by digest (the same images as
`latest` when this was written). To use another version, clear the digests too,
because they only match 2.1.0:

```shell
$ helm install --set image.version=2.0.2 --set image.digests=null ...
```

## Pod Security Policy

If you wish to enable [PSP](https://kubernetes.io/docs/concepts/policy/pod-security-policy/)

```shell
$ helm install --set psp.enabled=true ...
```

## Payment Gateway

By default the `payment` service uses https://www.paypal.com as the pseudo payment provider. The code only does a HTTP GET against this url. You can use a different url.

```shell
$ helm install --set payment.gateway=https://foobar.com ...
```

## Instana settings removed

This fork (for a DevOps capstone) removes the Instana agent environment
variable (`INSTANA_AGENT_HOST`) and the Instana end-user monitoring settings
(`eum.key`, `eum.url`) from the chart. Monitoring is done with Prometheus,
Loki and Jaeger instead.

The application images still contain the Instana libraries. With no agent
present they keep retrying and log messages such as:

- web: `Error: lookup requests for all agent host candidates failed`
- catalogue, cart and user: `Agent cannot be contacted via 127.0.0.1:42699 ...`
  (warning level)
- dispatch: `instana: ERROR: cannot connect to the agent ...`

These messages do not affect the shop. Removing them would mean rebuilding five
images, so they are kept. The log pipeline excludes them from error-level
searches, and that filter is documented with the logging configuration.

## Load generator

The chart deploys the `rs-load` traffic generator by default:

```shell
$ helm install robot-shop --set loadgen.clients=10 --set loadgen.errors=true ...
```

## Use with Minis

When running on `minishift` or `minikube` set `nodeport` to true. The store will then be available on the IP address of your mini and node port of the web service.

```shell
$ mini[kube|shift] ip
192.168.66.101
$ kubectl get svc web
```

Combine the IP and port number to make the URL `http://192.168.66.101:32145`

### MiniShift

Openshift is like K8s but not K8s. Set `openshift` to true or things will break. See the notes and scripts in the OpenShift directory of this repo.

```shell
$ helm install robot-shop --set openshift=true helm
```

## Deployment Parameters

| Key              | Default | Type   | Description |
| ---------------- | ------- | ------ | ----------- |
| image.pullPolicy | IfNotPresent | string | Kubernetes pull policy. One of Always,IfNotPresent, or Never. |
| image.repo       | robotshop | string | Base docker repository to pull the images from. |
| image.version    | 2.1.0 | string | Docker tag to pull. |
| image.digests.`<image>` | sha256 for 2.1.0 | string | Digest pinned for each image. Update or remove when changing `image.version`. |
| loadgen.enabled  | true | boolean | Deploy the `rs-load` traffic generator. |
| loadgen.host     | http://traefik.traefik.svc.cluster.local | url | Where the generator sends traffic (through Traefik, so it is measured per API). Use http://web:8080 if Traefik is not installed. Leave off the trailing slash, or requests become `//api/...`. |
| ingress.enabled  | true | boolean | Create an Ingress with one route per API in front of `web`. |
| ingress.className | traefik | string | IngressClass that serves the routes (Traefik, installed with `monitoring/traefik-values.yaml`). |
| ingress.apiPaths | catalogue, cart, payment, user, shipping, ratings | list | APIs that get their own `/api/<name>` route; everything else goes through `/`. |
| loadgen.clients  | 5 | integer | Number of simulated users. |
| loadgen.runTime  | 3m | duration | Length of each Locust run; load-gen restarts it in a loop so Locust's per-URL statistics (and memory) are reset. |
| loadgen.errors   | false | boolean | Also send a deliberately bad payment request (upstream's `ERROR=1`). |
| rabbitmq.image   | rabbitmq:3.7-management-alpine@sha256:... | string | RabbitMQ image, pinned by digest. |
| redis.image      | redis:4.0.6@sha256:... | string | Redis image, pinned by digest. |
| nodeport         | false | booelan | Whether to expose the services via node port. |
| openshift        | false | boolean | If OpenShift additional configuration is applied. |
| payment.gateway  | null | string | External URL end-point to simulate partial/3rd party traces. |
| payment.image    | "" | string | Full image reference that replaces `robotshop/rs-payment`, e.g. `robot-shop/rs-payment:2.1.0-otel` built from `payment/Dockerfile.otel`. |
| payment.tracing.enabled | false | boolean | Send OpenTelemetry traces from payment (needs the OTel image above and a collector, see `tracing/README.md`). |
| payment.tracing.endpoint | http://otel-collector.tracing.svc.cluster.local:4318 | url | OTLP/HTTP endpoint of the collector. |
| psp.enabled      | false | boolean | Enable Pod Security Policy. PodSecurityPolicy was removed in Kubernetes 1.25, so leave this false on current clusters. |
| redis.storageClassName | standard | string | Storage class to use with Redis's StatefulSet. The default for EKS is gp2. |
| ocCreateRoute    | false | boolean | If you are running on OpenShift and need a Route to the web service, set this to `true` |
| `<workload>`.affinity    | {} | object | Affinity for pod assignment on nodes with matching labels (Refer [here](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#affinity-and-anti-affinity)) |
| `<workload>`.nodeSelector    | {} | object | Node labels for pod assignment (Refer [here](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#nodeselector)) |
| `<workload>`.tolerations    | [] | list | Tolerations for pod assignment on nodes with matching taints (Refer [here](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)) |
---
> ### Notes for `affinity` and `tolerations`
> `<workload>` can be substituted with the different microservices consisting of Robot shop, namely:
> - [`cart`](./templates/cart-deployment.yaml)
> - [`catalogue`](./templates/catalogue-deployment.yaml)
> - [`dispatch`](./templates/dispatch-deployment.yaml)
> - [`mongodb`](./templates/mongodb-deployment.yaml)
> - [`mysql`](./templates/mysql-deployment.yaml)
> - [`payment`](./templates/payment-deployment.yaml)
> - [`rabbitmq`](./templates/rabbitmq-deployment.yaml)
> - [`ratings`](./templates/ratings-deployment.yaml)
> - [`redis`](./templates/redis-statefulset.yaml)
> - [`shipping`](./templates/shipping-deployment.yaml)
> - [`user`](./templates/user-deployment.yaml)
> - [`web`](./templates/web-deployment.yaml)
>
> `affinity`, `nodeSelector` and `tolerations` can be set for individual workloads.
------
## Examples for deployment using `affinities` and `tolerations`
<br />

`values.yaml`
```yaml
.
..
...
shipping:
    gateway: null
    affinity:
        nodeAffinity:
        requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
            - matchExpressions:
                - key: node-restriction.kubernetes.io/pool_0
                    operator: Exists
                    values: []
    tolerations:
        - key: "pool_0"
        operator: "Equal"
        value: "true"
        effect: "NoSchedule"
        - key: "pool_0"
        operator: "Equal"
        value: "true"
        effect: "NoExecute"
    nodeSelector: {}

user:
    affinity:
        nodeAffinity:
        requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
            - matchExpressions:
                - key: node-restriction.kubernetes.io/pool_1
                    operator: Exists
                    values: []
    tolerations:
        - key: "pool_1"
        operator: "Equal"
        value: "true"
        effect: "NoSchedule"
        - key: "pool_1"
        operator: "Equal"
        value: "true"
        effect: "NoExecute"
    nodeSelector: {}
...
..
.
 ```

In this example, the `shipping` Pods will be deployed on only those nodes that have the label `node-restriction.kubernetes.io/pool_0` and are tainted using
```
kubectl taint node <node_name> pool_0=true:NoSchedule
kubectl taint node <node_name> pool_0=true:NoExecute
```

Similarly, the `user` Pods will be deployed on only those nodes that have the label `node-restriction.kubernetes.io/pool_1` and are tainted using
```
kubectl taint node <node_name> pool_1=true:NoSchedule
kubectl taint node <node_name> pool_1=true:NoExecute
```

Hence, this way we can control which `Robot shop` workloads are running on which nodes/nodepools.

> *Note*: `nodeSelector` will behave in a similar fashion.
